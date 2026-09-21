import { useQuery } from "@tanstack/react-query";
import { useState, useCallback } from "react";
import { apiClient } from "@/api/client.ts";
import { useAuth } from "@/context/auth-context.tsx";

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

// ── API call ────────────────────────────────────────────────────────────────

async function fetchPhotos(filters: PhotosFilters): Promise<PhotoRecord[]> {
  const params = new URLSearchParams();
  if (filters.branch_id) params.set("branch_id", String(filters.branch_id));
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  const qs = params.toString();
  return apiClient<PhotoRecord[]>(`/checklists/photos${qs ? `?${qs}` : ""}`);
}

// ── Signed-URL helper ───────────────────────────────────────────────────────

export async function getSignedPhotoUrl(filename: string): Promise<string> {
  const data = await apiClient<{ url: string; expires_at: string }>(
    `/checklists/photos/${filename}/signed-url`,
  );
  return data.url;
}

// ── Page component ──────────────────────────────────────────────────────────

import { useRef } from "react";
import {
  Camera,
  Download,
  Filter,
  Image as ImageIcon,
  X,
  ZoomIn,
} from "lucide-react";
import { format } from "date-fns";
import { ru } from "date-fns/locale";

import { getMyProfile } from "@/api/employees.ts";
import { getBranches } from "@/api/branches.ts";
import type { BranchListItem } from "@/api/branches.ts";
import { Button } from "@/components/ui/button.tsx";
import { Card, CardContent } from "@/components/ui/card.tsx";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select.tsx";
import { Input } from "@/components/ui/input.tsx";
import { Badge } from "@/components/ui/badge.tsx";
import { Skeleton } from "@/components/ui/skeleton.tsx";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog.tsx";

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
  const { data: signedData } = useQuery({
    queryKey: ["photo-signed", photo.url],
    queryFn: () => {
      const filename = photo.url.split("/").pop() ?? "";
      return getSignedPhotoUrl(filename);
    },
    staleTime: 50 * 60 * 1000, // 50 min — token TTL is 60 min
    gcTime: 60 * 60 * 1000,
  });

  return (
    <Card
      className="group overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => onOpen(photo)}
    >
      <div className="relative aspect-square bg-muted overflow-hidden">
        {signedData ? (
          <img
            src={signedData}
            alt={photo.item_title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <ImageIcon className="size-10 text-muted-foreground" />
          </div>
        )}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
          <ZoomIn className="size-6 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
      <CardContent className="p-3 space-y-1">
        <p className="text-sm font-medium truncate" title={photo.item_title}>
          {photo.item_title}
        </p>
        <p className="text-xs text-muted-foreground truncate">
          {photo.checklist_name}
        </p>
        <div className="flex items-center justify-between gap-2">
          <Badge variant="secondary" className="text-xs">
            {photo.branch_name}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {format(new Date(photo.created_at), "dd MMM", { locale: ru })}
          </span>
        </div>
      </CardContent>
    </Card>
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
  if (!photo) return null;

  const handleDownload = () => {
    if (!signedUrl) return;
    const a = document.createElement("a");
    a.href = signedUrl;
    a.download = photo.url.split("/").pop() ?? "photo.jpg";
    a.click();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-3xl p-0 overflow-hidden">
        <DialogHeader className="sr-only">
          <DialogTitle>{photo.item_title}</DialogTitle>
        </DialogHeader>
        <div className="relative">
          {signedUrl ? (
            <img
              src={signedUrl}
              alt={photo.item_title}
              className="w-full max-h-[70vh] object-contain bg-black"
            />
          ) : (
            <div className="w-full h-64 flex items-center justify-center bg-muted">
              <ImageIcon className="size-16 text-muted-foreground" />
            </div>
          )}
          <button
            type="button"
            onClick={onClose}
            className="absolute top-2 right-2 rounded-full bg-black/60 p-1 text-white hover:bg-black/80 transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="p-4 space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="font-semibold truncate">{photo.item_title}</p>
              <p className="text-sm text-muted-foreground truncate">
                {photo.checklist_name}
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleDownload}
              disabled={!signedUrl}
              className="shrink-0"
            >
              <Download className="size-4 mr-1.5" />
              Скачать
            </Button>
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
                {format(new Date(photo.date + "T00:00:00"), "dd MMMM yyyy", {
                  locale: ru,
                })}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Загрузил:</span>{" "}
              <span>{photo.uploaded_by_name}</span>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
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
  branches: BranchListItem[];
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
          <Select
            value={filters.branch_id ? String(filters.branch_id) : "all"}
            onValueChange={(v) =>
              onChange({ branch_id: v === "all" ? undefined : Number(v) })
            }
          >
            <SelectTrigger className="w-44">
              <SelectValue placeholder="Все филиалы" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все филиалы</SelectItem>
              {branches.map((b) => (
                <SelectItem key={b.id} value={String(b.id)}>
                  {b.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">Дата от</span>
        <Input
          type="date"
          value={filters.date_from ?? ""}
          onChange={(e) =>
            onChange({ date_from: e.target.value || undefined })
          }
          className="w-36"
        />
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">Дата до</span>
        <Input
          type="date"
          value={filters.date_to ?? ""}
          onChange={(e) => onChange({ date_to: e.target.value || undefined })}
          className="w-36"
        />
      </div>

      {hasActive && (
        <Button variant="ghost" size="sm" onClick={onReset} className="gap-1">
          <X className="size-3.5" />
          Сбросить
        </Button>
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
    queryFn: getBranches,
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
    queryFn: () => {
      const filename = lightboxPhoto!.url.split("/").pop() ?? "";
      return getSignedPhotoUrl(filename);
    },
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
    <div className="p-4 md:p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Camera className="size-6 text-primary shrink-0" />
        <div>
          <h1 className="text-xl font-semibold">Фотоотчёты</h1>
          <p className="text-sm text-muted-foreground">
            Фотографии, прикреплённые к пунктам чек-листов
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-start gap-2">
        <Filter className="size-4 text-muted-foreground mt-2.5 shrink-0" />
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
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="aspect-square rounded-lg" />
          ))}
        </div>
      ) : !photos || photos.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-muted-foreground">
          <Camera className="size-12" />
          <p className="text-base font-medium">Фотографий нет</p>
          <p className="text-sm">
            Фотографии появятся здесь после их прикрепления к пунктам чек-листов
          </p>
        </div>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Найдено: {photos.length} фото
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
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
