"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { type ReactNode } from "react";
import { cn } from "@/lib/utils";

type DrawerProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
  className?: string;
};

export function Drawer({ open, onOpenChange, title, children, className }: DrawerProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/55 backdrop-blur-sm" />
        <Dialog.Content
          className={cn(
            "fixed right-0 top-0 z-50 h-screen w-[460px] border-l border-white/10 bg-[#0a1330]/95 p-4 text-[#dce9ff] shadow-[0_18px_60px_rgba(0,0,0,.5)]",
            "data-[state=open]:animate-fade-in-up",
            className,
          )}
        >
          <div className="mb-3 flex items-center justify-between">
            <Dialog.Title className="title-display text-xl">{title}</Dialog.Title>
            <Dialog.Close className="focus-ring rounded-md p-1 text-[#9eb6de] hover:bg-white/10 hover:text-white">
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>
          <div className="h-[calc(100vh-76px)] overflow-y-auto pr-2">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
