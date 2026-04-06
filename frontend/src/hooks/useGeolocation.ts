import { useState, useEffect, useRef } from 'react';

interface GeolocationState {
  latitude: number | null;
  longitude: number | null;
  accuracy: number | null;
  heading: number | null;
  speed: number | null;
  loading: boolean;
  error: string | null;
}

export function useGeolocation(options?: PositionOptions) {
  const [state, setState] = useState<GeolocationState>({
    latitude: null,
    longitude: null,
    accuracy: null,
    heading: null,
    speed: null,
    loading: true,
    error: null,
  });

  const watchIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (!navigator.geolocation) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: 'Geolocation stöds inte av din webbläsare',
      }));
      return;
    }

    const onSuccess = (position: GeolocationPosition) => {
      setState({
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy,
        heading: position.coords.heading,
        speed: position.coords.speed,
        loading: false,
        error: null,
      });
    };

    const onError = (error: GeolocationPositionError) => {
      let message: string;
      switch (error.code) {
        case error.PERMISSION_DENIED:
          message = 'Platsåtkomst nekad. Aktivera GPS i inställningar.';
          break;
        case error.POSITION_UNAVAILABLE:
          message = 'Platsinformation otillgänglig.';
          break;
        case error.TIMEOUT:
          message = 'GPS-förfrågan tog för lång tid.';
          break;
        default:
          message = 'Ett okänt GPS-fel uppstod.';
      }
      setState((prev) => ({
        ...prev,
        loading: false,
        error: message,
      }));
    };

    const defaultOptions: PositionOptions = {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 5000,
      ...options,
    };

    // Get initial position
    navigator.geolocation.getCurrentPosition(onSuccess, onError, defaultOptions);

    // Start watching
    watchIdRef.current = navigator.geolocation.watchPosition(
      onSuccess,
      onError,
      defaultOptions,
    );

    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
  }, []);

  return state;
}
