"use client";

import React, { useState, useRef, useCallback } from "react";
import { Upload, File, X, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface ResumeUploadProps {
  onUpload: (file: File) => Promise<void>;
  onSuccess?: (candidateData: Record<string, unknown>) => void;
  maxSizeMB?: number;
  acceptedFormats?: string[];
  multiple?: boolean;
}

type UploadState = "idle" | "dragging" | "uploading" | "parsing" | "success" | "error";

interface UploadFile {
  file: File;
  state: UploadState;
  progress: number;
  error?: string;
}

export function ResumeUpload({
  onUpload,
  onSuccess,
  maxSizeMB = 10,
  acceptedFormats = [".pdf", ".doc", ".docx"],
  multiple = false,
}: ResumeUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    const ext = `.${file.name.split(".").pop()?.toLowerCase()}`;
    if (!acceptedFormats.includes(ext)) {
      return `Invalid format. Accepted: ${acceptedFormats.join(", ")}`;
    }
    if (file.size > maxSizeMB * 1024 * 1024) {
      return `File too large. Max size: ${maxSizeMB}MB`;
    }
    return null;
  };

  const processFile = useCallback(
    async (file: File) => {
      const error = validateFile(file);
      const uploadFile: UploadFile = {
        file,
        state: error ? "error" : "uploading",
        progress: 0,
        error: error || undefined,
      };

      setUploadFiles((prev) => [...prev, uploadFile]);

      if (error) return;

      // Simulate progress
      const interval = setInterval(() => {
        setUploadFiles((prev) =>
          prev.map((f) =>
            f.file === file && f.state === "uploading" && f.progress < 70
              ? { ...f, progress: f.progress + 10 }
              : f
          )
        );
      }, 200);

      try {
        await onUpload(file);
        clearInterval(interval);

        // Switch to parsing state
        setUploadFiles((prev) =>
          prev.map((f) =>
            f.file === file ? { ...f, state: "parsing", progress: 80 } : f
          )
        );

        // Simulate parsing
        await new Promise((r) => setTimeout(r, 1500));

        setUploadFiles((prev) =>
          prev.map((f) =>
            f.file === file ? { ...f, state: "success", progress: 100 } : f
          )
        );

        onSuccess?.({ fileName: file.name, parsed: true });
      } catch (err) {
        clearInterval(interval);
        setUploadFiles((prev) =>
          prev.map((f) =>
            f.file === file
              ? { ...f, state: "error", error: "Upload failed. Please try again." }
              : f
          )
        );
      }
    },
    [onUpload, onSuccess]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files);
      const toProcess = multiple ? files : [files[0]];
      toProcess.forEach(processFile);
    },
    [processFile, multiple]
  );

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const toProcess = multiple ? files : [files[0]];
    toProcess.forEach(processFile);
    e.target.value = "";
  };

  const removeFile = (file: File) => {
    setUploadFiles((prev) => prev.filter((f) => f.file !== file));
  };

  const hasFiles = uploadFiles.length > 0;

  return (
    <div className="space-y-3">
      {/* Drop Zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={cn(
          "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed transition-all duration-200 p-8 cursor-pointer",
          isDragging
            ? "border-primary-500 bg-primary-50 dark:bg-primary-900/10 scale-[1.01]"
            : "border-border bg-muted/30 hover:border-primary-400 hover:bg-primary-50/50 dark:hover:bg-primary-900/5"
        )}
        onClick={() => fileInputRef.current?.click()}
      >
        <div
          className={cn(
            "flex h-14 w-14 items-center justify-center rounded-full mb-3 transition-colors",
            isDragging ? "bg-primary-100" : "bg-muted"
          )}
        >
          <Upload
            className={cn(
              "h-6 w-6 transition-colors",
              isDragging ? "text-primary-600" : "text-muted-foreground"
            )}
          />
        </div>
        <p className="text-sm font-semibold text-foreground mb-1">
          {isDragging ? "Drop to upload" : "Drag & drop resumes here"}
        </p>
        <p className="text-xs text-muted-foreground mb-3">
          or click to browse files
        </p>
        <div className="flex items-center gap-2">
          {acceptedFormats.map((fmt) => (
            <span
              key={fmt}
              className="text-xs bg-muted px-2 py-0.5 rounded font-medium text-muted-foreground uppercase"
            >
              {fmt.replace(".", "")}
            </span>
          ))}
          <span className="text-xs text-muted-foreground">up to {maxSizeMB}MB</span>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept={acceptedFormats.join(",")}
          multiple={multiple}
          className="hidden"
          onChange={handleFileInput}
        />
      </div>

      {/* Upload Progress */}
      {hasFiles && (
        <div className="space-y-2">
          {uploadFiles.map((uf, index) => (
            <div
              key={index}
              className="flex items-center gap-3 rounded-lg border border-border bg-background p-3"
            >
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-lg flex-shrink-0",
                  uf.state === "error"
                    ? "bg-danger-100"
                    : uf.state === "success"
                    ? "bg-success-100"
                    : "bg-primary-100"
                )}
              >
                {uf.state === "error" ? (
                  <AlertCircle className="h-4 w-4 text-danger-600" />
                ) : uf.state === "success" ? (
                  <CheckCircle className="h-4 w-4 text-success-600" />
                ) : uf.state === "parsing" ? (
                  <Loader2 className="h-4 w-4 text-primary-600 animate-spin" />
                ) : (
                  <File className="h-4 w-4 text-primary-600" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-xs font-medium text-foreground truncate">
                    {uf.file.name}
                  </p>
                  <span className="text-xs text-muted-foreground ml-2 flex-shrink-0">
                    {(uf.file.size / 1024 / 1024).toFixed(1)}MB
                  </span>
                </div>

                {uf.state === "error" ? (
                  <p className="text-xs text-danger-600">{uf.error}</p>
                ) : uf.state === "parsing" ? (
                  <p className="text-xs text-primary-600 animate-pulse">
                    AI parsing resume...
                  </p>
                ) : uf.state === "success" ? (
                  <p className="text-xs text-success-600">
                    Parsed successfully
                  </p>
                ) : (
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary-500 rounded-full transition-all duration-300"
                        style={{ width: `${uf.progress}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground w-8 text-right">
                      {uf.progress}%
                    </span>
                  </div>
                )}
              </div>

              <button
                onClick={() => removeFile(uf.file)}
                className="flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors ml-1"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Quick stats hint */}
      <p className="text-xs text-muted-foreground text-center">
        AI will automatically extract name, skills, experience, education & contact details
      </p>
    </div>
  );
}
