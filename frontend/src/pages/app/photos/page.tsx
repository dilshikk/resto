import { useQuery } from "@tanstack/react-query";
import { useState, useCallback } from "react";
import {
  Camera,
  Download,
  Filter,
  Image as ImageIcon,
  X,
  ZoomIn,
} from "lucide-react";

import { apiClient } from "@/api/client.ts";
import { useAuth } from "@/context/auth-context.tsx";
import { getMyProfile } from "@/api/employees.ts";
import { listBranches } from "@/api/branches.ts";
import type { Branch } from "@/api/branches.ts";
import { getPhotoSignedUrl } from "@/api/checklists.ts";

// ── Types ──────────────────────────────────────────────────────────────────

export interface PhotoRecord {
  id: number;
  checklist_id: number;
  checklist_name: string;
  item_id: number;
  item_title: string;
  branch_id: number;
  branch_name: string;
  shift: string;
  date: string;
  uploaded_by_name: string;
  url: string;
  created_at: string;
}

export interface PhotosFilters {
  branch_id?: number;
  date_from?: string;
  date_to?: string;
}

// ── Date formatting helpers ─────────────────────────────────────────────────
// The project has no date-fns dependency; use the built-in Intl API instead.

const shortDateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "short",
});

const longDateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "long",
  year: "numeric",
});

// ── API call ────────────────────────────────────────────────────────────────

async function fetchPhotos(filters: PhotosFilters): Promise<PhotoRecord[]> {
  const params: Record<string, string | number> = {};
  if (filters.branch_id) params.branch_id = filters.branch_id;
  if (filters.date_from) params.date_from = filters.date_from;
  if (filters.date_to) params.date_to = filters.date_to;
  const res = await apiClient.get<PhotoRecord[]>("/checklists/photos", {
    params,
  });
  return res.data;
}

// ── Photo card ─────────────────────────────────────────────────────────────

function PhotoCard({
  photo,
  onOpen,
}: {
  photo: PhotoRecord;
  onOpen: (photo: PhotoRecord) => void;
}) {
  // Build the authenticated URL for the img src: use the signed-url endpoint
  // so the image is served with a time-limited HMAC token.
  const { data: signedUrl } = useQuery({
    queryKey: ["photo-signed", photo.url],
    queryFn: () => getPhotoSignedUrl(photo.url),
    staleTime: 50 * 60 * 1000, // 50 min — token TTL is 60 min
    gcTime: 60 * 60 * 1000,
  });

  return (
    <div
      className="group cursor-pointer overflow-hidden rounded-xl border bg-card shadow-sm transition-shadow hover:shadow-md"
      onClick={() => onOpen(photo)}
    >
      <div className="relative aspect-square overflow-hidden bg-muted">
        {signedUrl ? (
          <img
            src={signedUrl}
            alt={photo.item_title}
            className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <ImageIcon className="size-10 text-muted-foreground" />
          </div>
        )}
        <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover:bg-black/20">
          <ZoomIn className="size-6 text-white opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
      </div>
      <div className="space-y-1 p-3">
        <p className="truncate text-sm font-medium" title={photo.item_title}>
          {photo.item_title}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {photo.checklist_name}
        </p>
        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
            {photo.branch_name}
          </span>
          <span className="text-xs text-muted-foreground">
            {shortDateFormatter.format(new Date(photo.created_at))}
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Lightbox ───────────────────────────────────────────────────────────────

function PhotoLightbox({
  photo,
  signedUrl,
  open,
  onClose,
}: {
  photo: PhotoRecord | null;
  signedUrl: string | undefined;
  open: boolean;
  onClose: () => void;
}) {
  if (!open || !photo) return null;

  const handleDownload = () => {
    if (!signedUrl) return;
    const a = document.createElement("a");
    a.href = signedUrl;
    a.download = photo.url.split("/").pop() ?? "photo.jpg";
    a.click();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-3xl overflow-hidden rounded-2xl border bg-card shadow-xl">
        <div className="relative">
          {signedUrl ? (
            <img
              src={signedUrl}
              alt={photo.item_title}
              className="max-h-[70vh] w-full bg-black object-contain"
            />
          ) : (
            <div className="flex h-64 w-full items-center justify-center bg-muted">
              <ImageIcon className="size-16 text-muted-foreground" />
            </div>
          )}
          <button
            type="button"
            onClick={onClose}
            className="absolute top-2 right-2 rounded-full bg-black/60 p-1 text-white transition-colors hover:bg-black/80"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="space-y-3 p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="truncate font-semibold">{photo.item_title}</p>
              <p className="truncate text-sm text-muted-foreground">
                {photo.checklist_name}
              </p>
            </div>
            <button
              type="button"
              onClick={handleDownload}
              disabled={!signedUrl}
              className="flex shrink-0 items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
            >
              <Download className="size-4" />
              Скачать
            </button>
          </div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
            <div>
              <span className="text-muted-foreground">Филиал:</span>{" "}
              <span>{photo.branch_name}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Смена:</span>{" "}
              <span>{photo.shift}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Дата:</span>{" "}
              <span>
                {longDateFormatter.format(new Date(`${photo.date}T00:00:00`))}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Загрузил:</span>{" "}
              <span>{photo.uploaded_by_name}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Filters bar ────────────────────────────────────────────────────────────

function FiltersBar({
  filters,
  branches,
  onChange,
  onReset,
  isManager,
}: {
  filters: PhotosFilters;
  branches: Branch[];
  onChange: (f: Partial<PhotosFilters>) => void;
  onReset: () => void;
  isManager: boolean;
}) {
  const hasActive =
    !!filters.branch_id || !!filters.date_from || !!filters.date_to;

  return (
    <div className="flex flex-wrap items-end gap-3">
      {isManager && (
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Филиал</span>
          <select
            className="w-44 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            value={filters.branch_id ? String(filters.branch_id) : "all"}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
              onChange({
                branch_id:
                  e.target.value === "all" ? undefined : Number(e.target.value),
              })
            }
          >
            <option value="all">Все филиалы</option>
            {branches.map((b) => (
              <option key={b.id} value={String(b.id)}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">Дата от</span>
        <input
          type="date"
          value={filters.date_from ?? ""}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            onChange({ date_from: e.target.value || undefined })
          }
          className="w-36 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">Дата до</span>
        <input
          type="date"
          value={filters.date_to ?? ""}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            onChange({ date_to: e.target.value || undefined })
          }
          className="w-36 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {hasActive && (
        <button
          type="button"
          onClick={onReset}
          className="flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X className="size-3.5" />
          Сбросить
        </button>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function PhotosPage() {
  const { isAuthenticated } = useAuth();
  const [filters, setFilters] = useState<PhotosFilters>({});
  const [lightboxPhoto, setLightboxPhoto] = useState<PhotoRecord | null>(null);

  const { data: profile } = useQuery({
    queryKey: ["my-profile"],
    queryFn: getMyProfile,
    enabled: isAuthenticated,
  });

  const isManager = (profile?.role_level ?? 0) >= 1;

  const { data: branches = [] } = useQuery({
    queryKey: ["branches"],
    queryFn: listBranches,
    enabled: isAuthenticated && isManager,
  });

  const { data: photos, isLoading } = useQuery({
    queryKey: ["photos", filters],
    queryFn: () => fetchPhotos(filters),
    enabled: isAuthenticated,
  });

  // Signed URL for the lightbox photo
  const { data: lightboxSignedUrl } = useQuery({
    queryKey: ["photo-signed", lightboxPhoto?.url],
    queryFn: () => getPhotoSignedUrl(lightboxPhoto!.url),
    enabled: !!lightboxPhoto,
    staleTime: 50 * 60 * 1000,
  });

  const handleFilterChange = useCallback(
    (patch: Partial<PhotosFilters>) =>
      setFilters((f) => ({ ...f, ...patch })),
    [],
  );

  const handleReset = useCallback(() => setFilters({}), []);

  return (
    <div className="space-y-5 p-4 md:p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Camera className="size-6 shrink-0 text-primary" />
        <div>
          <h1 className="text-xl font-semibold">Фотоотчёты</h1>
          <p className="text-sm text-muted-foreground">
            Фотографии, прикреплённые к пунктам чек-листов
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-start gap-2">
        <Filter className="mt-2.5 size-4 shrink-0 text-muted-foreground" />
        <FiltersBar
          filters={filters}
          branches={branches}
          onChange={handleFilterChange}
          onReset={handleReset}
          isManager={isManager}
        />
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {Array.from({ length: 10 }).map((_, i) => (
            <div
              key={i}
              className="aspect-square animate-pulse rounded-xl border bg-muted"
            />
          ))}
        </div>
      ) : !photos || photos.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
          <Camera className="size-12" />
          <p className="text-base font-medium">Фотографий нет</p>
          <p className="text-sm">
            Фотографии появятся здесь после их прикрепления к пунктам
            чек-листов
          </p>
        </div>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Найдено: {photos.length} фото
          </p>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {photos.map((photo) => (
              <PhotoCard
                key={`${photo.checklist_id}-${photo.item_id}-${photo.id}`}
                photo={photo}
                onOpen={setLightboxPhoto}
              />
            ))}
          </div>
        </>
      )}

      {/* Lightbox */}
      <PhotoLightbox
        photo={lightboxPhoto}
        signedUrl={lightboxSignedUrl}
        open={!!lightboxPhoto}
        onClose={() => setLightboxPhoto(null)}
      />
    </div>
  );
}
