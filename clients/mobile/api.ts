import Constants from 'expo-constants';

export interface TripRequestPayload {
  nationality: string;
  residence_country: string;
  departure_city: string;
  destination_countries: string[];
  start_date: string;
  end_date: string;
  purpose: string;
  budget_band?: 'low' | 'medium' | 'high';
  travellers_count?: number;
  traveller_names?: string[];
  notes?: string | null;
}

function getBaseUrl() {
  return (
    Constants.expoConfig?.extra?.apiBaseUrl ||
    Constants.manifest2?.extra?.apiBaseUrl ||
    'http://127.0.0.1:8000'
  );
}

export async function createVisaPack(payload: TripRequestPayload) {
  const res = await fetch(`${getBaseUrl()}/visa-pack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}`);
  }

  return res.json();
}
