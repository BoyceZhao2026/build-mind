import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "循循 · AI 数学陪练",
  description: "通过语音引导学生自己完成数学题",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
