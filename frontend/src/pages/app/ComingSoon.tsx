import { useEffect } from "react";
import { toast } from "sonner";

export default function ComingSoon({ title }: { title: string }) {
  useEffect(() => {
    toast("Скоро в следующем этапе!");
  }, []);

  return (
    <div className="flex h-full min-h-[60vh] flex-col items-center justify-center gap-2 px-4 text-center">
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="text-muted-foreground">Этот раздел появится в следующем обновлении.</p>
    </div>
  );
}
