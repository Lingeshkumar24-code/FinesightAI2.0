import React from "react";

interface CardProps {
  title?: string;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}

export function Card({ title, className = "", style, children }: CardProps) {
  return (
    <div className={`card${className ? ` ${className}` : ""}`} style={style}>
      {title && <h3 style={{ marginBottom: "12px" }}>{title}</h3>}
      {children}
    </div>
  );
}
