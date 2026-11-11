import { useMutation } from "@tanstack/react-query";
import type { FilePurpose } from "../model/types";
import { createUpload, putToStorage, confirmUpload } from "./endpoints";

export function useUploadFile(purpose: FilePurpose) {
  return useMutation({
    mutationFn: async (file: File) => {
      const created = await createUpload(purpose, file);
      await putToStorage(created.upload, file);
      return confirmUpload(created.file_id);
    },
    retry: false,
  });
}
