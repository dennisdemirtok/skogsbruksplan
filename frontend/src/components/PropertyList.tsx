import { useEffect, useState, useRef } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { usePropertyStore } from '@/store/propertyStore';
import { useForm } from 'react-hook-form';
import { geodataApi } from '@/services/api';
import { formatArea } from '@/utils/formatters';
import type { Property } from '@/types';
import {
  Plus,
  MapPin,
  Search,
  X,
  ArrowRight,
  Loader2,
  Trash2,
  Building2,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

interface NewPropertyForm {
  name: string;
  propertyDesignation: string;
  municipality: string;
  county: string;
}

export default function PropertyList() {
  const {
    properties,
    propertiesLoading,
    fetchProperties,
    createProperty,
    deleteProperty,
    saving,
  } = usePropertyStore();

  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const showNewForm = searchParams.get('action') === 'new';
  const [lookingUp, setLookingUp] = useState(false);
  const [lookupStatus, setLookupStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [lookupError, setLookupError] = useState('');
  const lookupGeometryRef = useRef<unknown>(null);
  const lookupAreaRef = useRef<number | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<NewPropertyForm>();

  useEffect(() => {
    fetchProperties();
  }, [fetchProperties]);

  const filteredProperties = properties.filter((p) => {
    const q = search.toLowerCase();
    return (
      (p.name || '').toLowerCase().includes(q) ||
      (p.propertyDesignation || '').toLowerCase().includes(q) ||
      (p.municipality || '').toLowerCase().includes(q)
    );
  });

  const onSubmitNew = async (data: NewPropertyForm) => {
    try {
      // Map frontend form fields to backend API fields
      const payload: Record<string, unknown> = {
        designation: data.propertyDesignation,
        municipality: data.municipality,
        county: data.county,
      };
      // If we have geometry from lookup, include it
      if (lookupGeometryRef.current) {
        payload.geometry_geojson = lookupGeometryRef.current;
      }
      if (lookupAreaRef.current) {
        payload.total_area_ha = lookupAreaRef.current;
      }

      const property = await createProperty(payload as Partial<Property>);
      lookupGeometryRef.current = null;
      lookupAreaRef.current = null;
      setSearchParams({});
      navigate(`/properties/${property.id}`);
    } catch {
      // error handled in store
    }
  };

  const handleLookup = async (designation: string) => {
    if (!designation) return;
    setLookingUp(true);
    setLookupStatus('idle');
    setLookupError('');
    lookupGeometryRef.current = null;
    lookupAreaRef.current = null;
    try {
      const result = await geodataApi.lookupProperty(designation);
      // Fill in form fields from the lookup response
      if (result.municipality) setValue('municipality', result.municipality);
      if (result.county) setValue('county', result.county);
      // Use designation as name if name field is empty
      const nameInput = document.querySelector<HTMLInputElement>('[name="name"]');
      if (nameInput && !nameInput.value) {
        setValue('name', result.designation || designation);
      }
      // Store geometry and area for when the form is submitted
      if (result.geometry) {
        lookupGeometryRef.current = result.geometry;
      }
      if (result.areaHa) {
        lookupAreaRef.current = result.areaHa;
      }
      setLookupStatus('success');
    } catch (err) {
      setLookupStatus('error');
      setLookupError(err instanceof Error ? err.message : 'Kunde inte slå upp fastigheten');
    } finally {
      setLookingUp(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-6 py-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fastigheter</h1>
          <p className="mt-1 text-sm text-gray-500">
            {properties.length} registrerade fastigheter
          </p>
        </div>
        <button
          onClick={() => setSearchParams({ action: 'new' })}
          className="flex items-center gap-2 rounded-lg bg-forest-700 px-4 py-2 text-sm font-medium text-white hover:bg-forest-800"
        >
          <Plus className="h-4 w-4" />
          Ny fastighet
        </button>
      </div>

      {/* New property form */}
      {showNewForm && (
        <div className="mb-6 rounded-xl border border-forest-200 bg-forest-50 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-forest-900">Ny fastighet</h2>
            <button
              onClick={() => setSearchParams({})}
              className="rounded-md p-1 text-gray-400 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <form onSubmit={handleSubmit(onSubmitNew)} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Fastighetsbeteckning
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
                    placeholder="Kommun Trakt 1:1"
                    {...register('propertyDesignation', { required: 'Krävs' })}
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const el = document.querySelector<HTMLInputElement>('[name="propertyDesignation"]');
                      if (el) handleLookup(el.value);
                    }}
                    disabled={lookingUp}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                  >
                    {lookingUp ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Slå upp'}
                  </button>
                </div>
                {errors.propertyDesignation && (
                  <p className="mt-1 text-xs text-red-600">{errors.propertyDesignation.message}</p>
                )}
                {lookupStatus === 'success' && (
                  <p className="mt-1 flex items-center gap-1 text-xs text-green-600">
                    <CheckCircle2 className="h-3 w-3" />
                    Fastighet hittad{lookupAreaRef.current ? ` — ${lookupAreaRef.current.toFixed(1)} ha` : ''}
                  </p>
                )}
                {lookupStatus === 'error' && (
                  <p className="mt-1 flex items-center gap-1 text-xs text-amber-600">
                    <AlertCircle className="h-3 w-3" />
                    {lookupError || 'Kunde inte slå upp fastigheten'}
                  </p>
                )}
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Namn</label>
                <input
                  type="text"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
                  placeholder="Min skogsfastighet"
                  {...register('name', { required: 'Krävs' })}
                />
                {errors.name && (
                  <p className="mt-1 text-xs text-red-600">{errors.name.message}</p>
                )}
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Kommun</label>
                <input
                  type="text"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
                  placeholder="Kommun"
                  {...register('municipality', { required: 'Krävs' })}
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Län</label>
                <input
                  type="text"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
                  placeholder="Län"
                  {...register('county', { required: 'Krävs' })}
                />
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setSearchParams({})}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Avbryt
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-forest-700 px-4 py-2 text-sm font-medium text-white hover:bg-forest-800 disabled:opacity-50"
              >
                {saving ? 'Skapar...' : 'Skapa fastighet'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Search */}
      <div className="mb-4 relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Sök fastighet..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-lg border border-gray-300 py-2 pl-9 pr-4 text-sm focus:border-forest-500 focus:outline-none focus:ring-1 focus:ring-forest-500"
        />
      </div>

      {/* Properties list */}
      {propertiesLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-forest-600" />
        </div>
      ) : filteredProperties.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Building2 className="mb-4 h-12 w-12 text-gray-300" />
          <p className="text-sm text-gray-500">
            {search ? 'Inga fastigheter matchar din sökning' : 'Inga fastigheter registrerade ännu'}
          </p>
          {!search && (
            <button
              onClick={() => setSearchParams({ action: 'new' })}
              className="mt-3 text-sm font-medium text-forest-700 hover:text-forest-800"
            >
              Lägg till din första fastighet
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredProperties.map((property) => (
            <PropertyCard key={property.id} property={property} onDelete={deleteProperty} />
          ))}
        </div>
      )}
    </div>
  );
}

function PropertyCard({
  property,
  onDelete,
}: {
  property: Property;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="group flex items-center justify-between rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition hover:shadow-md">
      <Link to={`/properties/${property.id}`} className="flex flex-1 items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-forest-100 text-forest-700">
          <MapPin className="h-6 w-6" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-gray-800">{property.name}</h3>
          <p className="text-xs text-gray-500">
            {property.propertyDesignation} &middot; {property.municipality}, {property.county}
          </p>
        </div>
      </Link>

      <div className="flex items-center gap-4">
        <div className="text-right">
          <p className="text-sm font-semibold text-gray-800">{formatArea(property.totalArea)}</p>
          <p className="text-xs text-gray-500">Prod: {formatArea(property.productiveArea)}</p>
        </div>
        <button
          onClick={(e) => {
            e.preventDefault();
            if (window.confirm(`Vill du verkligen ta bort "${property.name}"?`)) {
              onDelete(property.id);
            }
          }}
          className="rounded-md p-1.5 text-gray-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover:opacity-100"
        >
          <Trash2 className="h-4 w-4" />
        </button>
        <Link to={`/properties/${property.id}`}>
          <ArrowRight className="h-5 w-5 text-gray-400" />
        </Link>
      </div>
    </div>
  );
}
