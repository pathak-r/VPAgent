export interface TravelerInput {
  name: string;
  nationality: string;
  residence_country: string;
}

export interface DestinationInput {
  country: string;
  city: string;
  nights: number;
}

export interface VPAgentRequest {
  travelers: TravelerInput[];
  departure_city: string;
  departure_iata?: string;
  trip_start_date: string;
  destinations: DestinationInput[];
  trip_theme?: string;
  primary_destination_country?: string;
  primary_destination_city?: string;
}

export interface FlightOptionResponse {
  airline: string;
  departure_time: string;
  arrival_time: string;
  price_eur: number;
  booking_url: string;
}

export interface HotelOptionResponse {
  name: string;
  address: string;
  star_rating: number;
  nightly_rate_eur: number;
  total_cost_eur: number;
  board_type: string;
  booking_url: string;
}

export interface VPAgentResponse {
  trip_start_date: string;
  trip_end_date: string;
  total_nights: number;
  destinations: DestinationInput[];
  primary_destination?: string;
  primary_destination_city?: string;
  outbound_flights: FlightOptionResponse[];
  return_flights: FlightOptionResponse[];
  hotels_by_city: Record<string, HotelOptionResponse[]>;
  insurance_options: {
    provider: string;
    coverage_eur: number;
    price_per_person_eur: number;
    booking_url: string;
  }[];
  cover_letter: string;
  itinerary_table: string;
  preview_markdown: string;
}

const DEFAULT_API_BASE_URL = 'http://localhost:8000';

export async function createVisaPack(
  payload: VPAgentRequest,
  baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL,
): Promise<VPAgentResponse> {
  const response = await fetch(`${baseUrl}/visa-pack/agent`, {
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
