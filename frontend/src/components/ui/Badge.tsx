import * as React from "react"

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "primary" | "secondary" | "outline" | "success" | "warning" | "error"
}

function Badge({
  className,
  variant = "primary",
  ...props
}: BadgeProps) {
  const variantClasses = {
    primary: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300",
    secondary: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
    outline: "border border-gray-300 text-gray-700 dark:border-gray-600 dark:text-gray-300",
    success: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
    warning: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
    error: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300"
  }

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${variantClasses[variant]} ${className || ''}`}
      {...props}
    />
  )
}

export { Badge } 