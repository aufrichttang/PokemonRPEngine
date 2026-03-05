import { cva, type VariantProps } from "class-variance-authority";
import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold tracking-wide",
  {
    variants: {
      variant: {
        default: "bg-white/12 text-[#dce9ff] border border-white/15",
        primary: "bg-[#1b4f97] text-[#cfe6ff] border border-[#2f73cf]",
        violet: "bg-[#402f88] text-[#ded8ff] border border-[#705de0]",
        green: "bg-[#1e5f57] text-[#d5fff7] border border-[#37d6c8]",
        orange: "bg-[#7a4b19] text-[#ffe9c8] border border-[#ffb347]",
        red: "bg-[#7b2346] text-[#ffd5e3] border border-[#ff5c7a]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>;

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
