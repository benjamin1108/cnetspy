import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  eyebrow?: string;
  description?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}

export function PageHeader({ 
  title, 
  eyebrow, 
  description, 
  children, 
  className 
}: PageHeaderProps) {
  return (
    <div className={cn("flex flex-col md:flex-row justify-between items-start md:items-end gap-4 mb-8 pb-6 border-b border-border/40 animate-in fade-in slide-in-from-top-4 duration-500", className)}>
      <div className="space-y-1">
        {eyebrow && (
          <div className="text-xs font-bold tracking-[0.2em] text-primary mb-2 uppercase font-mono flex items-center gap-2">
            <span className="w-2 h-2 bg-primary/50 rounded-full animate-pulse" />
            {eyebrow}
          </div>
        )}
        <h1 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          {title}
        </h1>
        {description && (
          <div className="mt-2 text-sm text-muted-foreground max-w-2xl leading-relaxed">
            {description}
          </div>
        )}
      </div>
      {children && (
        <div className="flex flex-wrap items-center gap-2 mt-4 md:mt-0">
          {children}
        </div>
      )}
    </div>
  );
}
