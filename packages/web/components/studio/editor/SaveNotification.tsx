import { AnimatePresence, motion } from "motion/react";
import { bannerSlideVariants } from "@/lib/motion-variants";

interface SaveNotificationProps {
  readonly message: string;
}

export function SaveNotification({ message }: SaveNotificationProps) {
  return (
    <AnimatePresence>
      <motion.div
        variants={bannerSlideVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="mx-4 mb-2 px-3 py-2 rounded-lg bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs font-medium text-center"
      >
        {message}
      </motion.div>
    </AnimatePresence>
  );
}
