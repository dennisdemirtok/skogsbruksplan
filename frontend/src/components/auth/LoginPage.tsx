import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useAuthStore } from '@/store/authStore';
import { TreePine, Eye, EyeOff } from 'lucide-react';

interface LoginFormData {
  email: string;
  password: string;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, loading, error, clearError } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>();

  const onSubmit = async (data: LoginFormData) => {
    clearError();
    try {
      await login(data.email, data.password);
      navigate('/', { replace: true });
    } catch {
      // error is set in store
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-forest-900 via-forest-800 to-forest-700 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-forest-600 shadow-lg">
            <TreePine className="h-9 w-9 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white">SkogsplanSaaS</h1>
          <p className="mt-1 text-forest-200">Digital skogsbruksplanering</p>
        </div>

        {/* Form card */}
        <div className="rounded-xl bg-white p-8 shadow-2xl">
          <h2 className="mb-6 text-xl font-semibold text-gray-800">Logga in</h2>

          {error && (
            <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
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

            {/* Password */}
            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-medium text-gray-700">
                Lösenord
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  className="w-full rounded-lg border border-gray-300 px-4 py-2.5 pr-10 text-sm shadow-sm transition focus:border-forest-500 focus:outline-none focus:ring-2 focus:ring-forest-500/20"
                  placeholder="Ange ditt lösenord"
                  {...register('password', {
                    required: 'Lösenord krävs',
                    minLength: {
                      value: 6,
                      message: 'Lösenordet måste vara minst 6 tecken',
                    },
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

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-forest-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-forest-800 focus:outline-none focus:ring-2 focus:ring-forest-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'Loggar in...' : 'Logga in'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-gray-500">
            Har du inget konto?{' '}
            <Link to="/register" className="font-medium text-forest-700 hover:text-forest-800">
              Registrera dig
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
