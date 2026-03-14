import { cn } from '~/utils';

interface GitHubBadgeProps {
  className?: string;
}

export default function GitHubBadge({ className }: GitHubBadgeProps) {
  return (
    <a
      href="https://github.com/Backboard-io/Nash"
      target="_blank"
      rel="noopener noreferrer"
      className={cn('inline-flex items-center', className)}
      aria-label="View Nash on GitHub"
    >
      <img
        src="https://img.shields.io/github/stars/Backboard-io/Nash?style=social"
        alt="GitHub Stars"
        className="h-5"
      />
    </a>
  );
}
