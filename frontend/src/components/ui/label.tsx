"use client"

import * as React from "react"

export interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {
  htmlFor?: string
}

const Label = React.forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, htmlFor, ...props }, ref) => {
    return (
      <label
        ref={ref}
        htmlFor={htmlFor}
        className={`text-sm font-medium text-gray-700 dark:text-gray-300 ${className || ''}`}
        {...props}
      />
    )
  }
)
Label.displayName = "Label"

export { Label } 