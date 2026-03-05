import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => {
    return (
      <input
        className={cn(
          "h-10 w-full rounded-xl border border-[#2f4e84] bg-[#0d1936] px-3 text-sm text-[#e8f1ff] placeholder:text-[#6f86b2] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4da3ff]",
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);

Input.displayName = "Input";

export { Input };
