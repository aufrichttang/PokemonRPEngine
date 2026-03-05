import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Noto_Sans_SC, ZCOOL_QingKe_HuangYou } from "next/font/google";
import "./globals.css";
import Providers from "./providers";

const notoSans = Noto_Sans_SC({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-body",
  display: "swap",
});

const zcoolDisplay = ZCOOL_QingKe_HuangYou({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Pokemon RP Adventure",
  description: "Pokemon RP 玩家桌面冒险端",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className={`${notoSans.variable} ${zcoolDisplay.variable}`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
