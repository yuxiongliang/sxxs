import { describe, expect, it } from 'vitest';
import access from './access';

const ADMIN_PERMISSIONS = [
  'dashboard:read',
  'im:conversation:read',
  'payout:read',
  'seller:read',
];

const PRO_FEATURES = ['portal', 'im', 'finance', 'commission'];

function build(payload: {
  permissions?: string[];
  roles?: string[];
  features?: string[];
}) {
  return access({ permissions: payload.permissions ?? [], roles: payload.roles ?? [], features: payload.features });
}

describe('plan feature gates', () => {
  it('opens the paid modules when the plan lists them and the user may read them', () => {
    const result = build({ permissions: ADMIN_PERMISSIONS, features: PRO_FEATURES });
    expect(result.canUsePortal).toBe(true);
    expect(result.canUseIm).toBe(true);
    expect(result.canUseFinance).toBe(true);
  });

  it('hides paid modules on the free plan even when the user holds the permission', () => {
    const result = build({ permissions: ADMIN_PERMISSIONS, features: ['portal'] });
    expect(result.canUsePortal).toBe(true);
    expect(result.canImRead).toBe(true);
    expect(result.canUseIm).toBe(false);
    expect(result.canUseFinance).toBe(false);
  });

  it('still requires the permission when the plan unlocks the module', () => {
    const result = build({ permissions: ['dashboard:read'], features: PRO_FEATURES });
    expect(result.canUseIm).toBe(false);
    expect(result.canUseFinance).toBe(false);
  });

  it('fails open when the plan is unknown so an outage cannot lock the console', () => {
    const result = build({ permissions: ADMIN_PERMISSIONS });
    expect(result.canUsePortal).toBe(true);
    expect(result.canUseIm).toBe(true);
    expect(result.canUseFinance).toBe(true);
  });

  it('honours an explicitly empty feature list', () => {
    const result = build({ permissions: ADMIN_PERMISSIONS, features: [] });
    expect(result.canUsePortal).toBe(false);
    expect(result.canUseIm).toBe(false);
    expect(result.canUseFinance).toBe(false);
  });
});
