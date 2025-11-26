export type BudgetBand = 'low' | 'medium' | 'high';

export interface TripRequestPayload {
  nationality: string;
  residence_country: string;
  departure_city: string;
  destination_countries: string[];
  primary_destination_country: string;
  start_date: string;
  end_date: string;
  purpose: string;
  budget_band: BudgetBand;
  travellers_count: number;
  traveller_names?: string[];
  notes?: string | null;
}

const DEFAULT_API_BASE_URL = 'http://localhost:8000';

export async function createVisaPack(
  payload: TripRequestPayload,
  baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL,
) {
  const response = await fetch(`${baseUrl}/visa-pack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(`API error (${response.status}): ${message}`);
  }

  return response.json();
}
