import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { crossfadeVariants } from "@/lib/motion-variants";

export function EditorEmptyState() {
  const t = useTranslations("studio");

  return (
    <motion.div
      variants={crossfadeVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      className="flex-1 flex items-center justify-center h-full text-muted-foreground"
    >
      <p>{t("editor.selectChapter")}</p>
    </motion.div>
  );
}

export function EditorLoadingState() {
  return (
    <motion.div
      variants={crossfadeVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      className="flex-1 flex items-center justify-center h-full"
    >
      <div className="w-8 h-8 rounded-md bg-primary animate-pulse" />
    </motion.div>
  );
}
