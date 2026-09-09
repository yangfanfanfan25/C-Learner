const DATABASE_NAME = 'my-rag-ui';
const DATABASE_VERSION = 1;
const STORE_NAME = 'chat-backgrounds';

export interface StoredBackground {
  id: string;
  label: string;
  blob: Blob;
  createdAt: number;
}

const openDatabase = (): Promise<IDBDatabase> =>
  new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);

    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: 'id' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('无法打开背景图库'));
  });

const runRequest = async <T>(
  mode: IDBTransactionMode,
  createRequest: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> => {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, mode);
    const request = createRequest(transaction.objectStore(STORE_NAME));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('背景图库操作失败'));
    transaction.oncomplete = () => database.close();
    transaction.onerror = () => database.close();
  });
};

export const listStoredBackgrounds = () =>
  runRequest<StoredBackground[]>('readonly', (store) => store.getAll());

export const saveStoredBackground = (background: StoredBackground) =>
  runRequest<IDBValidKey>('readwrite', (store) => store.put(background));

export const deleteStoredBackground = (id: string) =>
  runRequest<undefined>('readwrite', (store) => store.delete(id));
