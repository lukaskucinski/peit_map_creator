import React from 'react'
import { cn } from '@/lib/utils'
import styles from './stacking-loader.module.css'

interface StackingLoaderProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: number // Size in pixels (default: 56)
  caption?: string // Optional caption text
  showCaption?: boolean // Show/hide caption
}

export function StackingLoader({
  size = 56,
  caption = 'Loading…',
  showCaption = false,
  className,
  ...props
}: StackingLoaderProps) {
  return (
    <div
      className={cn(styles.loader, className)}
      role="status"
      aria-label="Loading"
      style={
        {
          '--loader-size': `${size}px`,
        } as React.CSSProperties
      }
      {...props}
    >
      {/* Box 1 - Left entry */}
      <div className={`${styles.box} ${styles.box1}`}>
        <div className={styles.sideLeft}></div>
        <div className={styles.sideRight}></div>
        <div className={styles.sideTop}></div>
      </div>

      {/* Box 2 - Right entry */}
      <div className={`${styles.box} ${styles.box2}`}>
        <div className={styles.sideLeft}></div>
        <div className={styles.sideRight}></div>
        <div className={styles.sideTop}></div>
      </div>

      {/* Box 3 - Left entry */}
      <div className={`${styles.box} ${styles.box3}`}>
        <div className={styles.sideLeft}></div>
        <div className={styles.sideRight}></div>
        <div className={styles.sideTop}></div>
      </div>

      {/* Box 4 - Right entry */}
      <div className={`${styles.box} ${styles.box4}`}>
        <div className={styles.sideLeft}></div>
        <div className={styles.sideRight}></div>
        <div className={styles.sideTop}></div>
      </div>

      {/* Caption (optional) */}
      {showCaption && <div className={styles.caption}>{caption}</div>}
    </div>
  )
}
