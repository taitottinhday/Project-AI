import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function BaseIcon({ children, ...props }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height="20"
      viewBox="0 0 24 24"
      width="20"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {children}
    </svg>
  );
}

export function SparkIcon(props: IconProps) {
  return <BaseIcon {...props}><path d="m12 3 1.3 4.2L17.5 8.5l-4.2 1.3L12 14l-1.3-4.2-4.2-1.3 4.2-1.3L12 3Z" stroke="currentColor" strokeLinejoin="round"/><path d="m18 14 .8 2.2L21 17l-2.2.8L18 20l-.8-2.2L15 17l2.2-.8L18 14Z" stroke="currentColor" strokeLinejoin="round"/></BaseIcon>;
}

export function ShieldIcon(props: IconProps) {
  return <BaseIcon {...props}><path d="M12 3 5 6v5c0 4.6 2.9 8.1 7 10 4.1-1.9 7-5.4 7-10V6l-7-3Z" stroke="currentColor" strokeWidth="1.7"/><path d="m9 12 2 2 4-4" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7"/></BaseIcon>;
}

export function SourceIcon(props: IconProps) {
  return <BaseIcon {...props}><path d="M7 3h8l3 3v15H7V3Z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.7"/><path d="M15 3v4h4M10 11h5M10 15h5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7"/></BaseIcon>;
}

export function ChatIcon(props: IconProps) {
  return <BaseIcon {...props}><path d="M5 5h14v11H9l-4 4V5Z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.7"/><path d="M9 9h6M9 12h4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7"/></BaseIcon>;
}

export function StaffIcon(props: IconProps) {
  return <BaseIcon {...props}><circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.7"/><path d="M5 21c.5-4.1 2.8-6.2 7-6.2s6.5 2.1 7 6.2" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7"/></BaseIcon>;
}

export function ArrowIcon(props: IconProps) {
  return <BaseIcon {...props}><path d="M5 12h14m-5-5 5 5-5 5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"/></BaseIcon>;
}

export function SendIcon(props: IconProps) {
  return <BaseIcon {...props}><path d="m4 4 17 8-17 8 3-8-3-8Z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.7"/><path d="M7 12h14" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7"/></BaseIcon>;
}

export function ExternalIcon(props: IconProps) {
  return <BaseIcon {...props}><path d="M14 5h5v5M19 5l-8 8" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7"/><path d="M18 13v6H5V6h6" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7"/></BaseIcon>;
}

export function ClockIcon(props: IconProps) {
  return <BaseIcon {...props}><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.7"/><path d="M12 7v5l3 2" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7"/></BaseIcon>;
}

export function CheckIcon(props: IconProps) {
  return <BaseIcon {...props}><path d="m5 12 4 4L19 6" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"/></BaseIcon>;
}

export function RefreshIcon(props: IconProps) {
  return <BaseIcon {...props}><path d="M20 7v5h-5M4 17v-5h5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7"/><path d="M18 12a6 6 0 0 0-10.5-4M6 12a6 6 0 0 0 10.5 4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7"/></BaseIcon>;
}

export function CloseIcon(props: IconProps) {
  return <BaseIcon {...props}><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8"/></BaseIcon>;
}

export function MenuIcon(props: IconProps) {
  return <BaseIcon {...props}><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8"/></BaseIcon>;
}

export function CopyIcon(props: IconProps) {
  return <BaseIcon {...props}><rect height="12" rx="2" stroke="currentColor" strokeWidth="1.6" width="12" x="8" y="8"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" stroke="currentColor" strokeWidth="1.6"/></BaseIcon>;
}
