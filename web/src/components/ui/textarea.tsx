import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          "w-full rounded-xl border border-[#2f4e84] bg-[#0d1936] px-3 py-2 text-sm leading-6 text-[#e8f1ff] placeholder:text-[#6f86b2] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4da3ff]",
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);

Textarea.displayName = "Textarea";

export { Textarea };
