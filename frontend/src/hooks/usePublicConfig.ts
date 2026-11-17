import { useEffect, useState } from 'react';
import { getPublicConfig, type PublicConfig } from '../lib/api';

const DEFAULT: PublicConfig = { uploads_enabled: true, demo_mode: false };

export function usePublicConfig(): PublicConfig {
  const [cfg, setCfg] = useState<PublicConfig>(DEFAULT);
  useEffect(() => {
    getPublicConfig().then(setCfg).catch(() => {});
  }, []);
  return cfg;
}
