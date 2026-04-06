import { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useAuthStore } from '@/store/authStore';
import { usePropertyStore } from '@/store/propertyStore';
import { Menu } from 'lucide-react';

export default function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const loadUser = useAuthStore((s) => s.loadUser);
  const fetchProperties = usePropertyStore((s) => s.fetchProperties);

  useEffect(() => {
    loadUser();
    fetchProperties();
  }, [loadUser, fetchProperties]);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Mobile sidebar overlay */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`
          fixed inset-y-0 left-0 z-40 lg:static lg:z-auto
          transform transition-transform duration-200 ease-in-out
          ${mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          onCloseMobile={() => setMobileSidebarOpen(false)}
        />
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-14 items-center gap-4 border-b border-gray-200 bg-white px-4 lg:px-6">
          <button
            className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 lg:hidden"
            onClick={() => setMobileSidebarOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>

          <PropertySelector />

          <div className="flex-1" />

          <div className="text-sm text-gray-500">
            SkogsplanSaaS
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function PropertySelector() {
  const properties = usePropertyStore((s) => s.properties);
  const currentProperty = usePropertyStore((s) => s.currentProperty);
  const fetchProperty = usePropertyStore((s) => s.fetchProperty);

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value;
    if (id) {
      fetchProperty(id);
    }
  };

  return (
    <select
      className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 shadow-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
      value={currentProperty?.id ?? ''}
      onChange={handleChange}
    >
      <option value="">Välj fastighet...</option>
      {properties.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name} ({p.propertyDesignation})
        </option>
      ))}
    </select>
  );
}
