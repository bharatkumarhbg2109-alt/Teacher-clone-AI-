import { api } from "./api";

function putWithProgress(
  url: string,
  body: Blob,
  contentType: string,
  onProgress?: (pct: number) => void
): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", contentType);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress((e.loaded / e.total) * 100);
    };
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve(xhr.getResponseHeader("ETag") || "")
        : reject(new Error(`Upload failed (${xhr.status})`));
    xhr.onerror = () => reject(new Error("Upload network error"));
    xhr.send(body);
  });
}

/**
 * Upload via presigned POST (S3-enforced conditions: file size + Content-Type).
 * Returns the ETag-like string S3 responds with.
 */
function postWithProgress(
  url: string,
  fields: Record<string, string>,
  body: Blob,
  contentType: string,
  onProgress?: (pct: number) => void
): Promise<string> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    // Add all S3 fields first (key, policy, signature, etc.)
    for (const [k, v] of Object.entries(fields)) {
      formData.append(k, v);
    }
    // File blob must be last in a presigned POST form
    formData.append("file", body, "upload");

    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress((e.loaded / e.total) * 100);
    };
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve("")
        : reject(new Error(`Upload failed (${xhr.status})`));
    xhr.onerror = () => reject(new Error("Upload network error"));
    xhr.send(formData);
  });
}

/** Upload a file (single-shot or multipart) and kick off processing.
 * Returns the media_source_id. */
export async function uploadFile(
  file: File,
  teacherProfileId: string,
  onProgress?: (pct: number) => void
): Promise<string> {
  const contentType = file.type || "application/octet-stream";
  const init = await api<any>("/media/upload/initiate", {
    method: "POST",
    body: JSON.stringify({
      teacher_profile_id: teacherProfileId,
      file_name: file.name,
      file_size: file.size,
      content_type: contentType,
    }),
  });

  if (init.multipart_upload_id) {
    // Multipart (large files) — always uses presigned PUT per part.
    const partSize = init.part_size as number;
    const count = init.part_count as number;
    const partNumbers = Array.from({ length: count }, (_, i) => i + 1);
    const urls = await api<{ part_number: number; url: string }[]>("/media/upload/parts", {
      method: "POST",
      body: JSON.stringify({
        media_source_id: init.media_source_id,
        upload_key: init.upload_key,
        multipart_upload_id: init.multipart_upload_id,
        part_numbers: partNumbers,
      }),
    });
    const parts: { PartNumber: number; ETag: string }[] = [];
    for (const { part_number, url } of urls) {
      const start = (part_number - 1) * partSize;
      const blob = file.slice(start, Math.min(start + partSize, file.size));
      const etag = await putWithProgress(url, blob, contentType, (p) =>
        onProgress?.(((part_number - 1) / count) * 100 + p / count)
      );
      parts.push({ PartNumber: part_number, ETag: etag.replaceAll('"', "") });
    }
    await api("/media/upload/complete", {
      method: "POST",
      body: JSON.stringify({
        media_source_id: init.media_source_id,
        storage_key: init.upload_key,
        multipart_upload_id: init.multipart_upload_id,
        parts,
      }),
    });
  } else if (init.upload_fields) {
    // Single-shot via presigned POST (S3-enforced size + Content-Type conditions).
    await postWithProgress(init.upload_url, init.upload_fields, file, contentType, onProgress);
    await api("/media/upload/complete", {
      method: "POST",
      body: JSON.stringify({
        media_source_id: init.media_source_id,
        storage_key: init.upload_key,
      }),
    });
  } else {
    // Single-shot via presigned PUT (local backend fallback).
    await putWithProgress(init.upload_url, file, contentType, onProgress);
    await api("/media/upload/complete", {
      method: "POST",
      body: JSON.stringify({
        media_source_id: init.media_source_id,
        storage_key: init.upload_key,
      }),
    });
  }
  onProgress?.(100);
  return init.media_source_id;
}
