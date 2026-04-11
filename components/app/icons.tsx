import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function BaseIcon(props: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    />
  );
}

export function DashboardIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <rect x="3" y="3" width="8" height="8" rx="2" />
      <rect x="13" y="3" width="8" height="5" rx="2" />
      <rect x="13" y="10" width="8" height="11" rx="2" />
      <rect x="3" y="13" width="8" height="8" rx="2" />
    </BaseIcon>
  );
}

export function UsersIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M15 19c0-2.2-1.8-4-4-4s-4 1.8-4 4" />
      <circle cx="11" cy="9" r="3" />
      <path d="M19 19c0-1.7-1-3.1-2.5-3.7" />
      <path d="M16.5 6.5A2.5 2.5 0 0 1 16.5 11" />
    </BaseIcon>
  );
}

export function InputsIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <path d="M8 10h8" />
      <path d="M12 3v6" />
      <path d="m9.5 5.5 2.5-2.5 2.5 2.5" />
    </BaseIcon>
  );
}

export function ParcelsIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M4 6h16v12H4z" />
      <path d="M4 12h16" />
      <path d="M10 6v12" />
      <path d="M15 12v6" />
    </BaseIcon>
  );
}

export function ProductsIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M12 21c4.4-1.7 7-5.3 7-9.6C19 7.6 16 5 12 5S5 7.6 5 11.4C5 15.7 7.6 19.3 12 21Z" />
      <path d="M12 5V3" />
      <path d="M12 12c1.7-2.1 3.2-2.8 5-3" />
    </BaseIcon>
  );
}

export function StocksIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M4 8 12 4l8 4-8 4-8-4Z" />
      <path d="M4 8v8l8 4 8-4V8" />
      <path d="M12 12v8" />
    </BaseIcon>
  );
}

export function LotsIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <rect x="3" y="4" width="8" height="7" rx="1.5" />
      <rect x="13" y="4" width="8" height="7" rx="1.5" />
      <rect x="3" y="13" width="8" height="7" rx="1.5" />
      <rect x="13" y="13" width="8" height="7" rx="1.5" />
    </BaseIcon>
  );
}

export function TransformIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M4 7h11" />
      <path d="m11 4 4 3-4 3" />
      <path d="M20 17H9" />
      <path d="m13 14-4 3 4 3" />
    </BaseIcon>
  );
}

export function AnalyticsIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M4 19h16" />
      <rect x="6" y="11" width="3" height="6" rx="1" />
      <rect x="11" y="8" width="3" height="9" rx="1" />
      <rect x="16" y="5" width="3" height="12" rx="1" />
    </BaseIcon>
  );
}

export function SparkIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="m12 3 1.3 3.4L17 7.7l-3.7 1.3L12 12.5 10.7 9 7 7.7l3.7-1.3L12 3Z" />
      <path d="m18.5 13 0.7 1.8 1.8 0.7-1.8 0.7-0.7 1.8-0.7-1.8-1.8-0.7 1.8-0.7 0.7-1.8Z" />
    </BaseIcon>
  );
}

export function ChatIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M4 5h16v10H7l-3 4V5Z" />
      <path d="M8 9h8M8 12h5" />
    </BaseIcon>
  );
}

export function BellIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M6 9a6 6 0 1 1 12 0v4l2 2H4l2-2V9Z" />
      <path d="M10 19a2 2 0 0 0 4 0" />
    </BaseIcon>
  );
}

export function SearchIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.2-3.2" />
    </BaseIcon>
  );
}

export function WeatherIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M6 15a3.5 3.5 0 1 1 .5-6.9A4.5 4.5 0 0 1 15 10h.5a2.5 2.5 0 1 1 0 5H6Z" />
      <path d="M17.5 6.5h3" />
      <path d="M19 5v3" />
    </BaseIcon>
  );
}

export function MenuIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M4 7h16" />
      <path d="M4 12h16" />
      <path d="M4 17h16" />
    </BaseIcon>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="m6 6 12 12" />
      <path d="m18 6-12 12" />
    </BaseIcon>
  );
}

export function ChevronLeftIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="m15 18-6-6 6-6" />
    </BaseIcon>
  );
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="m9 18 6-6-6-6" />
    </BaseIcon>
  );
}

export function ChevronDownIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="m6 9 6 6 6-6" />
    </BaseIcon>
  );
}

export function SettingsIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 0 1-4 0v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 0 1 0-4h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 0 1 2.8-2.8l.1.1a1 1 0 0 0 1.1.2h.1a1 1 0 0 0 .6-.9V4a2 2 0 0 1 4 0v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a2 2 0 0 1 2.8 2.8l-.1.1a1 1 0 0 0-.2 1.1v.1a1 1 0 0 0 .9.6H20a2 2 0 0 1 0 4h-.2a1 1 0 0 0-.9.6Z" />
    </BaseIcon>
  );
}

export function HelpIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9.5a2.5 2.5 0 1 1 4.2 1.8c-.8.7-1.7 1.3-1.7 2.7" />
      <circle cx="12" cy="17" r="0.7" fill="currentColor" stroke="none" />
    </BaseIcon>
  );
}

export function LogoutIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5" />
      <path d="M21 12H9" />
    </BaseIcon>
  );
}

export function UserIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <circle cx="12" cy="8" r="3" />
      <path d="M5 20a7 7 0 0 1 14 0" />
    </BaseIcon>
  );
}

export function ProfileIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <circle cx="12" cy="8" r="3" />
      <path d="M4 20c1.7-3.3 4.3-5 8-5s6.3 1.7 8 5" />
    </BaseIcon>
  );
}

export function CooperativeIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M4 20h16" />
      <path d="M6 20V8l6-4 6 4v12" />
      <path d="M9 11h1" />
      <path d="M14 11h1" />
      <path d="M11 20v-4h2v4" />
    </BaseIcon>
  );
}

export function ManagerIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 19c.7-2.8 2.7-4.5 5.5-4.5s4.8 1.7 5.5 4.5" />
      <circle cx="17.5" cy="14.5" r="3.5" />
      <path d="M17.5 12.7v3.6" />
      <path d="M15.7 14.5h3.6" />
    </BaseIcon>
  );
}
