import { useState, useEffect, useCallback, useRef } from 'react';
import { openDB, type IDBPDatabase } from 'idb';
import { fieldDataApi } from '@/services/api';
import type { FieldData } from '@/types';

const DB_NAME = 'skogsplan-offline';
const DB_VERSION = 1;
const STORE_NAME = 'pending-fielddata';

async function getDb(): Promise<IDBPDatabase> {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
      }
    },
  });
}

interface OfflineSyncState {
  isOnline: boolean;
  pendingCount: number;
  syncing: boolean;
  lastSyncError: string | null;
  saveOffline: (data: Omit<FieldData, 'id' | 'synced'>) => Promise<void>;
  sync: () => Promise<void>;
}

export function useOfflineSync(): OfflineSyncState {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [pendingCount, setPendingCount] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [lastSyncError, setLastSyncError] = useState<string | null>(null);
  const dbRef = useRef<IDBPDatabase | null>(null);

  // Initialize DB and count pending
  useEffect(() => {
    const init = async () => {
      dbRef.current = await getDb();
      await updatePendingCount();
    };
    init();
  }, []);

  // Listen for online/offline events
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      // Auto-sync when coming back online
      sync();
    };
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const updatePendingCount = useCallback(async () => {
    try {
      const db = dbRef.current ?? (await getDb());
      const count = await db.count(STORE_NAME);
      setPendingCount(count);
    } catch {
      // ignore db errors
    }
  }, []);

  const saveOffline = useCallback(
    async (data: Omit<FieldData, 'id' | 'synced'>) => {
      try {
        const db = dbRef.current ?? (await getDb());
        await db.add(STORE_NAME, {
          ...data,
          savedAt: new Date().toISOString(),
        });
        await updatePendingCount();
      } catch (err) {
        console.error('Failed to save offline:', err);
        throw err;
      }
    },
    [updatePendingCount],
  );

  const sync = useCallback(async () => {
    if (syncing || !navigator.onLine) return;

    setSyncing(true);
    setLastSyncError(null);

    try {
      const db = dbRef.current ?? (await getDb());
      const allKeys = await db.getAllKeys(STORE_NAME);

      for (const key of allKeys) {
        const entry = await db.get(STORE_NAME, key);
        if (!entry) continue;

        try {
          // Remove the local-only fields before sending
          const { id: _id, savedAt: _savedAt, ...payload } = entry as Record<string, unknown>;
          const standId = (payload.standId as string) || '';
          await fieldDataApi.create(standId, payload as Partial<FieldData>);
          // Delete from local store on success
          await db.delete(STORE_NAME, key);
        } catch (err) {
          console.error('Failed to sync entry:', key, err);
          setLastSyncError(
            err instanceof Error ? err.message : 'Synkronisering misslyckades',
          );
          // Continue with next entry
        }
      }

      await updatePendingCount();
    } catch (err) {
      setLastSyncError(
        err instanceof Error ? err.message : 'Synkronisering misslyckades',
      );
    } finally {
      setSyncing(false);
    }
  }, [syncing, updatePendingCount]);

  return {
    isOnline,
    pendingCount,
    syncing,
    lastSyncError,
    saveOffline,
    sync,
  };
}
