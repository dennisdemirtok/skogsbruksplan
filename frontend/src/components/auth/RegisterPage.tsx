import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useAuthStore } from '@/store/authStore';
import { TreePine, Eye, EyeOff } from 'lucide-react';

interface RegisterFormData {
  name: string;
  email: string;
  password: string;
  confirmPassword: string;
  role: 'consultant' | 'owner';
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register: registerUser, loading, error, clearError } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterFormData>({
    defaultValues: { role: 'consultant' },
  });

  const password = watch('password');

  const onSubmit = async (data: RegisterFormData) => {
    clearError();
    try {
      await registerUser(data.name, data.email, data.password, data.role);
      navigate('/', { replace: true });
    } catch {
      // error is set in store
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-forest-900 via-forest-800 to-forest-700 px-4 py-8">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-forest-600 shadow-lg">
            <TreePine className="h-9 w-9 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white">SkogsplanSaaS</h1>
          <p className="mt-1 text-forest-200">Skapa ett konto</p>
        </div>

        {/* Form card */}
        <div className="rounded-xl bg-white p-8 shadow-2xl">
          <h2 className="mb-6 text-xl font-semibold text-gray-800">Registrera</h2>

          {error && (
            <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            {/* Name */}
            <div>
              <label htmlFor="name" className="mb-1 block text-sm font-medium text-gray-700">
                Namn
              </label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm shadow-sm transition focus:border-forest-500 focus:outline-none focus:ring-2 focus:ring-forest-500/20"
                placeholder="Ditt fullständiga namn"
                {...register('name', { required: 'Namn krävs' })}
              />
              {errors.name && (
                <p className="mt-1 text-xs text-red-600">{errors.name.message}</p>
              )}
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-medium text-gray-700">
                E-postadress
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm shadow-sm transition focus:border-forest-500 focus:outline-none focus:ring-2 focus:ring-forest-500/20"
                placeholder="namn@exempel.se"
                {...register('email', {
                  required: 'E-postadress krävs',
                  pattern: {
                    value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                    message: 'Ogiltig e-postadress',
                  },
                })}
              />
              {errors.email && (
                <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
              )}
            </div>

            {/* Role */}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Roll</label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    value="consultant"
                    className="h-4 w-4 border-gray-300 text-forest-600 focus:ring-forest-500"
                    {...register('role')}
                  />
                  <span className="text-sm text-gray-700">Konsult / Planerare</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    value="owner"
                    className="h-4 w-4 border-gray-300 text-forest-600 focus:ring-forest-500"
                    {...register('role')}
                  />
                  <span className="text-sm text-gray-700">Skogsägare</span>
                </label>
              </div>
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-medium text-gray-700">
                Lösenord
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  className="w-full rounded-lg border border-gray-300 px-4 py-2.5 pr-10 text-sm shadow-sm transition focus:border-forest-500 focus:outline-none focus:ring-2 focus:ring-forest-500/20"
                  placeholder="Minst 8 tecken"
                  {...register('password', {
                    required: 'Lösenord krävs',
                    minLength: { value: 8, message: 'Lösenordet måste vara minst 8 tecken' },
                  })}
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
              )}
            </div>

            {/* Confirm password */}
            <div>
              <label htmlFor="confirmPassword" className="mb-1 block text-sm font-medium text-gray-700">
                Bekräfta lösenord
              </label>
              <input
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm shadow-sm transition focus:border-forest-500 focus:outline-none focus:ring-2 focus:ring-forest-500/20"
                placeholder="Upprepa lösenordet"
                {...register('confirmPassword', {
                  required: 'Bekräftelse krävs',
                  validate: (val) => val === password || 'Lösenorden matchar inte',
                })}
              />
              {errors.confirmPassword && (
                <p className="mt-1 text-xs text-red-600">{errors.confirmPassword.message}</p>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-forest-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-forest-800 focus:outline-none focus:ring-2 focus:ring-forest-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'Skapar konto...' : 'Skapa konto'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-gray-500">
            Har du redan ett konto?{' '}
            <Link to="/login" className="font-medium text-forest-700 hover:text-forest-800">
              Logga in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
