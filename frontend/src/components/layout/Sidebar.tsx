import { NavLink, useParams } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { usePropertyStore } from '@/store/propertyStore';
import {
  LayoutDashboard,
  MapPin,
  Smartphone,
  Settings,
  Map,
  TreePine,
  Hammer,
  DollarSign,
  ClipboardList,
  ChevronLeft,
  ChevronRight,
  LogOut,
  X,
  TreesIcon,
} from 'lucide-react';
import clsx from 'clsx';

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  onCloseMobile: () => void;
}

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
}

export default function Sidebar({ collapsed, onToggleCollapse, onCloseMobile }: SidebarProps) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const currentProperty = usePropertyStore((s) => s.currentProperty);
  const { id: propertyIdParam } = useParams();
  const propertyId = currentProperty?.id ?? propertyIdParam;

  const mainNav: NavItem[] = [
    { to: '/', label: 'Dashboard', icon: <LayoutDashboard className="h-5 w-5" /> },
    { to: '/properties', label: 'Fastigheter', icon: <MapPin className="h-5 w-5" /> },
    { to: '/field', label: 'Fältapp', icon: <Smartphone className="h-5 w-5" /> },
  ];

  const propertyNav: NavItem[] = propertyId
    ? [
        { to: `/properties/${propertyId}`, label: 'Karta', icon: <Map className="h-5 w-5" /> },
        { to: `/properties/${propertyId}?tab=stands`, label: 'Avdelningar', icon: <TreePine className="h-5 w-5" /> },
        { to: `/properties/${propertyId}?tab=actions`, label: 'Åtgärder', icon: <Hammer className="h-5 w-5" /> },
        { to: `/properties/${propertyId}?tab=economy`, label: 'Ekonomi', icon: <DollarSign className="h-5 w-5" /> },
        { to: `/properties/${propertyId}?tab=plan`, label: 'Skogsbruksplan', icon: <ClipboardList className="h-5 w-5" /> },
      ]
    : [];

  return (
    <aside
      className={clsx(
        'flex h-full flex-col border-r border-gray-200 bg-forest-900 text-white transition-all duration-200',
        collapsed ? 'w-16' : 'w-64',
      )}
    >
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-forest-800 px-3">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <TreesIcon className="h-6 w-6 text-forest-300" />
            <span className="text-lg font-bold tracking-tight">Skogsplan</span>
          </div>
        )}
        {collapsed && (
          <TreesIcon className="mx-auto h-6 w-6 text-forest-300" />
        )}
        <button
          className="hidden rounded p-1 text-forest-300 hover:bg-forest-800 hover:text-white lg:block"
          onClick={onToggleCollapse}
          title={collapsed ? 'Expandera' : 'Minimera'}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
        <button
          className="rounded p-1 text-forest-300 hover:bg-forest-800 hover:text-white lg:hidden"
          onClick={onCloseMobile}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Main navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <ul className="space-y-1">
          {mainNav.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-forest-700 text-white'
                      : 'text-forest-200 hover:bg-forest-800 hover:text-white',
                    collapsed && 'justify-center',
                  )
                }
                title={collapsed ? item.label : undefined}
              >
                {item.icon}
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            </li>
          ))}
        </ul>

        {/* Property-specific navigation */}
        {propertyNav.length > 0 && (
          <>
            <div className="my-3 border-t border-forest-800" />
            {!collapsed && (
              <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-forest-400">
                {currentProperty?.name ?? 'Fastighet'}
              </p>
            )}
            <ul className="space-y-1">
              {propertyNav.map((item) => (
                <li key={item.to + item.label}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      clsx(
                        'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-forest-700 text-white'
                          : 'text-forest-200 hover:bg-forest-800 hover:text-white',
                        collapsed && 'justify-center',
                      )
                    }
                    title={collapsed ? item.label : undefined}
                  >
                    {item.icon}
                    {!collapsed && <span>{item.label}</span>}
                  </NavLink>
                </li>
              ))}
            </ul>
          </>
        )}

        {/* Settings */}
        <div className="my-3 border-t border-forest-800" />
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            clsx(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-forest-700 text-white'
                : 'text-forest-200 hover:bg-forest-800 hover:text-white',
              collapsed && 'justify-center',
            )
          }
          title={collapsed ? 'Inställningar' : undefined}
        >
          <Settings className="h-5 w-5" />
          {!collapsed && <span>Inställningar</span>}
        </NavLink>
      </nav>

      {/* User section */}
      <div className="border-t border-forest-800 p-3">
        <div
          className={clsx(
            'flex items-center',
            collapsed ? 'justify-center' : 'gap-3',
          )}
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-forest-600 text-sm font-semibold text-white">
            {user?.name?.charAt(0)?.toUpperCase() ?? '?'}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">{user?.name}</p>
              <p className="truncate text-xs text-forest-400">{user?.email}</p>
            </div>
          )}
          {!collapsed && (
            <button
              onClick={logout}
              className="rounded p-1 text-forest-400 hover:bg-forest-800 hover:text-white"
              title="Logga ut"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
