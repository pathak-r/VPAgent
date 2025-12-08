"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import {
  VPAgentRequest,
  VPAgentResponse,
  createVisaPack,
  DestinationInput,
} from "@/lib/api";

const SCHENGEN_REGIONS = [
  {
    name: "Western & Alpine Europe (The Classics)",
    description:
      "The traditional Western route: major capitals, alpine escapes, and fast rail networks.",
    countries: [
      { label: "🇦🇹 Austria", value: "Austria" },
      { label: "🇧🇪 Belgium", value: "Belgium" },
      { label: "🇫🇷 France", value: "France" },
      { label: "🇩🇪 Germany", value: "Germany" },
      { label: "🇱🇮 Liechtenstein", value: "Liechtenstein" },
      { label: "🇱🇺 Luxembourg", value: "Luxembourg" },
      { label: "🇳🇱 Netherlands", value: "Netherlands" },
      { label: "🇨🇭 Switzerland", value: "Switzerland" },
    ],
  },
  {
    name: "Southern Europe (Mediterranean & Sun)",
    description: "Warm coastlines, Roman/Greco heritage, and relaxed seaside cities.",
    countries: [
      { label: "🇭🇷 Croatia", value: "Croatia" },
      { label: "🇬🇷 Greece", value: "Greece" },
      { label: "🇮🇹 Italy", value: "Italy" },
      { label: "🇲🇹 Malta", value: "Malta" },
      { label: "🇵🇹 Portugal", value: "Portugal" },
      { label: "🇪🇸 Spain", value: "Spain" },
    ],
  },
  {
    name: "Northern Europe (The Nordics)",
    description:
      "Nature, cooler climates, and higher costs. Iceland and Norway are Schengen but not in the EU.",
    countries: [
      { label: "🇩🇰 Denmark", value: "Denmark" },
      { label: "🇫🇮 Finland", value: "Finland" },
      { label: "🇮🇸 Iceland", value: "Iceland" },
      { label: "🇳🇴 Norway", value: "Norway" },
      { label: "🇸🇪 Sweden", value: "Sweden" },
    ],
  },
  {
    name: "Central & Eastern Europe",
    description:
      "History-rich, budget-friendly, and newer Schengen additions (Baltics noted accordingly).",
    countries: [
      { label: "🇧🇬 Bulgaria (Newest Member)", value: "Bulgaria" },
      { label: "🇨🇿 Czechia", value: "Czechia" },
      { label: "🇪🇪 Estonia (Baltics)", value: "Estonia" },
      { label: "🇭🇺 Hungary", value: "Hungary" },
      { label: "🇱🇻 Latvia (Baltics)", value: "Latvia" },
      { label: "🇱🇹 Lithuania (Baltics)", value: "Lithuania" },
      { label: "🇵🇱 Poland", value: "Poland" },
      { label: "🇷🇴 Romania (Newest Member)", value: "Romania" },
      { label: "🇸🇰 Slovakia", value: "Slovakia" },
      { label: "🇸🇮 Slovenia", value: "Slovenia" },
    ],
  },
];

type CountryNights = Record<string, number>;

type FormState = {
  nationality: string;
  residence_country: string;
  departure_city: string;
  countryNights: CountryNights;
  primaryDestination: string;
  start_date: string;
  purpose: string;
  travellers_count: number;
  travellerNamesText: string;
  tripThemeSelection: string;
  tripThemeCustom: string;
};

const TRIP_THEME_LIMIT = 160;
const friendlyDateFormatter = new Intl.DateTimeFormat("en-US", {
  weekday: "long",
  month: "short",
  day: "numeric",
  year: "numeric",
});
const friendlyTimeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
});

const defaultForm: FormState = {
  nationality: "Indian",
  residence_country: "India",
  departure_city: "Bengaluru (BLR)",
  countryNights: { France: 5 },
  primaryDestination: "France",
  start_date: "2025-12-05",
  purpose: "tourism",
  travellers_count: 2,
  travellerNamesText: "Rohit Pathak, Vrushali Malushte",
  tripThemeSelection: "none",
  tripThemeCustom: "",
};

const fieldClasses =
  "mt-1 w-full rounded border border-slate-300 bg-white p-2 text-slate-900 placeholder-slate-400 focus:border-slate-500 focus:outline-none";
const textareaClasses = `${fieldClasses} min-h-[3rem]`;
const selectClasses = `${fieldClasses} cursor-pointer`;

const DEFAULT_CITY_BY_COUNTRY: Record<string, string> = {
  France: "Paris",
  Germany: "Berlin",
  Italy: "Rome",
  Spain: "Madrid",
  Netherlands: "Amsterdam",
  Belgium: "Brussels",
  Switzerland: "Zurich",
  Austria: "Vienna",
  Portugal: "Lisbon",
  Greece: "Athens",
  Czechia: "Prague",
  Poland: "Warsaw",
  Hungary: "Budapest",
  Sweden: "Stockholm",
  Finland: "Helsinki",
  Denmark: "Copenhagen",
  Norway: "Oslo",
  Croatia: "Zagreb",
  Bulgaria: "Sofia",
  Romania: "Bucharest",
  Slovakia: "Bratislava",
  Slovenia: "Ljubljana",
  Estonia: "Tallinn",
  Latvia: "Riga",
  Lithuania: "Vilnius",
  Luxembourg: "Luxembourg City",
  Malta: "Valletta",
  Iceland: "Reykjavik",
  Liechtenstein: "Vaduz",
};

function splitInput(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function parseDateValue(value?: string): Date | null {
  if (!value) return null;
  if (value.includes("T")) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const parts = value.split("-");
  if (parts.length !== 3) return null;
  const [year, month, day] = parts.map((part) => Number(part));
  if (!year || !month || !day) return null;
  const date = new Date(year, month - 1, day);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDateDisplay(value?: string): string {
  const parsed = parseDateValue(value);
  if (!parsed) return value ?? "";
  return friendlyDateFormatter.format(parsed);
}

function formatDateTimeDisplay(value?: string): string {
  const parsed = parseDateValue(value);
  if (!parsed) return value ?? "";
  return `${friendlyDateFormatter.format(parsed)}, ${friendlyTimeFormatter.format(parsed)}`;
}

export default function Home() {
  const [form, setForm] = useState<FormState>(defaultForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VPAgentResponse | null>(null);

  const selectedCountries = useMemo(() => Object.keys(form.countryNights), [form.countryNights]);
  const selectedCount = selectedCountries.length;

  const totalNights = useMemo(
    () => selectedCountries.reduce((sum, country) => sum + (form.countryNights[country] ?? 0), 0),
    [form.countryNights, selectedCountries],
  );

  const topNights = useMemo(() => {
    if (!selectedCountries.length) {
      return 0;
    }
    return Math.max(...selectedCountries.map((c) => form.countryNights[c] ?? 0));
  }, [form.countryNights, selectedCountries]);

  const tiedPrimaryCountries = useMemo(() => {
    if (!selectedCountries.length) {
      return [];
    }
    return selectedCountries.filter((c) => (form.countryNights[c] ?? 0) === topNights);
  }, [form.countryNights, selectedCountries, topNights]);

  const autoPrimary = useMemo(() => {
    if (!selectedCountries.length) {
      return "";
    }
    return selectedCountries.reduce((best, current) => {
      const bestNights = form.countryNights[best] ?? 0;
      const currentNights = form.countryNights[current] ?? 0;
      if (currentNights > bestNights) {
        return current;
      }
      return best;
    }, selectedCountries[0]);
  }, [form.countryNights, selectedCountries]);

  useEffect(() => {
    if (!selectedCountries.length) {
      setForm((prev) => ({ ...prev, primaryDestination: "" }));
      return;
    }
    if (tiedPrimaryCountries.length > 1) {
      if (!tiedPrimaryCountries.includes(form.primaryDestination)) {
        setForm((prev) => ({ ...prev, primaryDestination: tiedPrimaryCountries[0] }));
      }
    } else {
      const auto = autoPrimary;
      if (auto && form.primaryDestination !== auto) {
        setForm((prev) => ({ ...prev, primaryDestination: auto }));
      }
    }
  }, [autoPrimary, form.primaryDestination, selectedCountries, tiedPrimaryCountries]);


  const computedEndDate = useMemo(() => {
    if (!form.start_date || totalNights <= 0) {
      return "";
    }
    const start = new Date(form.start_date);
    const end = new Date(start);
    end.setDate(start.getDate() + totalNights);
    return end.toISOString().split("T")[0];
  }, [form.start_date, totalNights]);

  const handleInput = (key: keyof typeof form) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      setForm((prev) => ({ ...prev, [key]: event.target.value }));
    };

  const handleNumberInput = (key: keyof typeof form) =>
    (event: ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [key]: Number(event.target.value) }));
    };

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!selectedCountries.length) {
      setError("Select at least one destination country.");
      return;
    }

    if (!form.primaryDestination) {
      setError("Choose the primary country where you'll spend the most nights.");
      return;
    }

    setLoading(true);

    const customText = form.tripThemeCustom.trim();
    let tripTheme: string | undefined;
    if (form.tripThemeSelection === "custom") {
      tripTheme = customText || undefined;
    } else if (form.tripThemeSelection && form.tripThemeSelection !== "none") {
      tripTheme = form.tripThemeSelection;
    } else if (customText) {
      tripTheme = customText;
    }

    const travelerNames = splitInput(form.travellerNamesText);
    const resolvedNames =
      travelerNames.length > 0 ? travelerNames : ["Primary Traveler"];
    const travelers = resolvedNames.map((name) => ({
      name,
      nationality: form.nationality,
      residence_country: form.residence_country,
    }));

    const destinations: DestinationInput[] = selectedCountries.map((country) => ({
      country,
      city: DEFAULT_CITY_BY_COUNTRY[country] ?? country,
      nights: form.countryNights[country] ?? 1,
    }));

    const payload: VPAgentRequest = {
      travelers,
      departure_city: form.departure_city,
      trip_start_date: form.start_date,
      destinations,
      trip_theme: tripTheme,
      primary_destination_country: form.primaryDestination || destinations[0]?.country,
      primary_destination_city:
        DEFAULT_CITY_BY_COUNTRY[form.primaryDestination || destinations[0]?.country || ""] ||
        destinations[0]?.city,
    };

    try {
      const response = await createVisaPack(payload);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 py-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4">
        <section className="rounded-lg bg-white p-6 shadow text-slate-900">
          <h1 className="mb-4 text-2xl font-semibold text-slate-900">Visa Pack Generator</h1>
          <p className="mb-6 text-sm text-slate-700">
            Fill in the travel details and submit to call the FastAPI backend. This helps validate
            upcoming agent updates before shipping a polished product.
          </p>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="text-sm font-medium text-slate-900">
                Nationality
                <input
                  className={fieldClasses}
                  value={form.nationality}
                  onChange={handleInput("nationality")}
                  required
                />
              </label>
              <label className="text-sm font-medium text-slate-900">
                Residence Country
                <input
                  className={fieldClasses}
                  value={form.residence_country}
                  onChange={handleInput("residence_country")}
                  required
                />
              </label>
              <label className="text-sm font-medium text-slate-900">
                Departure City
                <input
                  className={fieldClasses}
                  value={form.departure_city}
                  onChange={handleInput("departure_city")}
                  required
                />
              </label>
              <label className="text-sm font-medium text-slate-900">
                Start Date
                <input
                  type="date"
                  className={fieldClasses}
                  value={form.start_date}
                  onChange={handleInput("start_date")}
                  required
                />
                {form.start_date && (
                  <div className="mt-1 text-xs text-slate-500">
                    {formatDateDisplay(form.start_date)}
                  </div>
                )}
              </label>
            </div>
            <div className="rounded border border-slate-200 p-4">
              <div className="mb-2 text-sm font-medium text-slate-900">Trip style (optional)</div>
              <div className="space-y-2 text-sm text-slate-700">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="trip-style"
                    value="The Gastronomic Tour"
                    checked={form.tripThemeSelection === "The Gastronomic Tour"}
                    onChange={(event) => setForm((prev) => ({ ...prev, tripThemeSelection: event.target.value }))}
                  />
                  The Gastronomic Tour (food-focused)
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="trip-style"
                    value="The Grand Tour"
                    checked={form.tripThemeSelection === "The Grand Tour"}
                    onChange={(event) => setForm((prev) => ({ ...prev, tripThemeSelection: event.target.value }))}
                  />
                  The Grand Tour (history & culture)
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="trip-style"
                    value="Gastronomy + Culture"
                    checked={form.tripThemeSelection === "Gastronomy + Culture"}
                    onChange={(event) => setForm((prev) => ({ ...prev, tripThemeSelection: event.target.value }))}
                  />
                  Gastronomy + Culture (balanced mix)
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="trip-style"
                    value="custom"
                    checked={form.tripThemeSelection === "custom"}
                    onChange={(event) => setForm((prev) => ({ ...prev, tripThemeSelection: event.target.value }))}
                  />
                  Custom focus
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="trip-style"
                    value="none"
                    checked={form.tripThemeSelection === "none"}
                    onChange={(event) => setForm((prev) => ({ ...prev, tripThemeSelection: event.target.value }))}
                  />
                  No preference
                </label>
              </div>
              {form.tripThemeSelection === "custom" && (
                <label className="mt-3 block text-sm font-medium text-slate-900">
                  Custom description (max {TRIP_THEME_LIMIT} chars)
                  <textarea
                    className={`${textareaClasses} mt-1`}
                    maxLength={TRIP_THEME_LIMIT}
                    value={form.tripThemeCustom}
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, tripThemeCustom: event.target.value }))
                    }
                    placeholder="E.g., art museums with vegan dining"
                  />
                  <span className="text-xs text-slate-500">
                    {form.tripThemeCustom.length}/{TRIP_THEME_LIMIT}
                  </span>
                </label>
              )}
            </div>
            <div>
              <div className="mb-2 text-sm font-medium text-slate-900">Schengen Destinations</div>
              <p className="mb-3 text-xs text-slate-500">
                Expand a region, toggle the countries you plan to visit, and assign the number of nights.
              </p>
              <div className="space-y-3">
                {SCHENGEN_REGIONS.map((region) => (
                  <details key={region.name} className="rounded border border-slate-200 bg-slate-50">
                    <summary className="cursor-pointer px-3 py-2 text-sm font-semibold">
                      <div>{region.name}</div>
                      <div className="text-xs font-normal text-slate-500">{region.description}</div>
                    </summary>
                    <div className="divide-y divide-slate-200">
                      {region.countries.map(({ label, value }) => {
                        const nights = form.countryNights[value];
                        const selected = typeof nights === "number";
                        return (
                          <div key={value} className="flex items-center justify-between px-3 py-2 text-sm">
                            <label className="flex items-center gap-2">
                              <input
                                type="checkbox"
                                className="h-4 w-4"
                                checked={selected}
                                onChange={() => {
                                  setForm((prev) => {
                                    const next = { ...prev.countryNights };
                                    if (selected) {
                                      delete next[value];
                                    } else {
                                      next[value] = 2;
                                    }
                                    return { ...prev, countryNights: next };
                                  });
                                }}
                              />
                              {label}
                            </label>
                            {selected && (
                              <div className="flex items-center gap-2">
                                <button
                                  type="button"
                                  className="rounded border border-slate-300 px-2 py-1 text-xs"
                                  onClick={() =>
                                    setForm((prev) => ({
                                      ...prev,
                                      countryNights: {
                                        ...prev.countryNights,
                                        [value]: Math.max(1, (prev.countryNights[value] ?? 1) - 1),
                                      },
                                    }))
                                  }
                                >
                                  −
                                </button>
                                <input
                                  type="number"
                                  min={1}
                                  className="w-16 rounded border border-slate-300 px-2 py-1 text-center text-sm"
                                  value={nights}
                                  onChange={(event) =>
                                    setForm((prev) => ({
                                      ...prev,
                                      countryNights: {
                                        ...prev.countryNights,
                                        [value]: Math.max(1, Number(event.target.value) || 1),
                                      },
                                    }))
                                  }
                                />
                                <button
                                  type="button"
                                  className="rounded border border-slate-300 px-2 py-1 text-xs"
                                  onClick={() =>
                                    setForm((prev) => ({
                                      ...prev,
                                      countryNights: {
                                        ...prev.countryNights,
                                        [value]: (prev.countryNights[value] ?? 1) + 1,
                                      },
                                    }))
                                  }
                                >
                                  +
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </details>
                ))}
              </div>

              {selectedCount === 0 ? (
                <p className="mt-2 text-xs text-red-600">Please select at least one destination.</p>
              ) : (
                <p className="mt-2 text-xs text-slate-500">
                  Selected {selectedCount} countries • Total nights: {totalNights}
                </p>
              )}
            </div>
            <label className="text-sm font-medium text-slate-900">
              Estimated End Date (auto-calculated)
              <input
                type="text"
                readOnly
                className={`${fieldClasses} bg-slate-100 text-slate-500`}
                value={
                  computedEndDate
                    ? formatDateDisplay(computedEndDate)
                    : "This updates as you add countries & nights."
                }
              />
            </label>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="text-sm font-medium text-slate-900">
                Primary Country (longest stay / first entry)
                <select
                  className={selectClasses}
                  value={form.primaryDestination}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, primaryDestination: event.target.value }))
                  }
                  disabled={tiedPrimaryCountries.length <= 1}
                  required
                >
                  {selectedCountries.length === 0 && <option value="">Select destinations first</option>}
                  {(tiedPrimaryCountries.length > 1 ? tiedPrimaryCountries : selectedCountries).map((country) => (
                    <option key={country} value={country}>
                      {country} ({form.countryNights[country]} nights)
                    </option>
                  ))}
                </select>
                {tiedPrimaryCountries.length > 1 ? (
                  <p className="mt-1 text-xs font-semibold text-orange-600">
                    Multiple countries share the longest stay. Pick the first country of entry.
                  </p>
                ) : (
                  <p className="mt-1 text-xs text-slate-500">Automatically set to the destination with the most nights.</p>
                )}
              </label>
              <div className="text-xs text-slate-500">
                The primary country must be your point of entry and longest stay. The cover letter addresses this consulate.
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="text-sm font-medium text-slate-900">
                Travellers Count
                <input
                  type="number"
                  min={1}
                  className={fieldClasses}
                  value={form.travellers_count}
                  onChange={handleNumberInput("travellers_count")}
                />
              </label>
              <p className="text-sm text-slate-600">
                Flights default to the cheapest nonstop/1-stop itineraries we can find, and hotels
                emphasize well-rated yet affordable stays.
              </p>
            </div>
            <label className="text-sm font-medium text-slate-900">
              Traveller Names (comma or newline separated)
              <textarea
                className={textareaClasses}
                value={form.travellerNamesText}
                onChange={handleInput("travellerNamesText")}
                rows={3}
              />
            </label>
            <button
              type="submit"
              className="w-full rounded bg-slate-900 py-3 text-white transition hover:bg-slate-800 disabled:opacity-50"
              disabled={loading}
            >
              {loading ? "Generating…" : "Generate Visa Pack"}
            </button>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </form>
        </section>
        <section className="rounded-lg bg-white p-6 shadow text-slate-900">
          <h2 className="mb-4 text-xl font-semibold text-slate-900">Response Preview</h2>
          {result ? (
            <div className="space-y-6">
              <div>
                <h3 className="font-medium">Cover Letter</h3>
                <pre className="mt-2 whitespace-pre-wrap rounded bg-indigo-50 p-3 text-sm text-slate-900">
                  {result.cover_letter}
                </pre>
              </div>

              <FlightSections outbound={result.outbound_flights} inbound={result.return_flights} />

              {Object.keys(result.hotels_by_city || {}).length > 0 && (
                <div>
                  <h3 className="font-medium">Hotel Suggestions</h3>
                  <div className="mt-2 space-y-4 text-sm">
                    {Object.entries(result.hotels_by_city).map(([city, hotels]) => (
                      <div key={city} className="rounded border border-slate-200 bg-white p-3 shadow-sm">
                        <div className="font-semibold">{city}</div>
                        <ul className="mt-2 list-disc pl-4 text-slate-700">
                          {hotels.map((hotel) => (
                            <li key={`${city}-${hotel.name}`}>
                              {hotel.name} · {hotel.star_rating}-star · €{hotel.nightly_rate_eur.toFixed(0)}/night ·{" "}
                              <a href={hotel.booking_url} target="_blank" rel="noreferrer" className="text-blue-600">
                                View
                              </a>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {result.insurance_options.length > 0 && (
                <div>
                  <h3 className="font-medium">Travel Insurance</h3>
                  <div className="mt-2 grid gap-3 md:grid-cols-2">
                    {result.insurance_options.map((plan) => (
                      <div key={plan.provider} className="rounded border border-slate-200 bg-white p-3 shadow-sm text-sm">
                        <div className="font-semibold">{plan.provider}</div>
                        <p>Coverage: €{plan.coverage_eur.toLocaleString()}</p>
                        <p>Price per traveler: €{plan.price_per_person_eur.toFixed(0)}</p>
                        <a className="text-blue-600" href={plan.booking_url} target="_blank" rel="noreferrer">
                          View policy
                        </a>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <h3 className="font-medium">Day-by-Day Itinerary</h3>
                <pre className="mt-2 whitespace-pre-wrap rounded border border-slate-200 bg-white p-3 text-sm text-slate-900">
                  {result.itinerary_table}
                </pre>
              </div>

              <div>
                <h3 className="font-medium">Preview Markdown</h3>
                <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded border border-slate-200 bg-white p-3 text-xs text-slate-900">
                  {result.preview_markdown}
                </pre>
              </div>

              <details className="rounded border border-slate-200 bg-white p-3 text-sm shadow-sm">
                <summary className="cursor-pointer font-medium">Raw JSON</summary>
                <pre className="mt-2 overflow-auto whitespace-pre bg-slate-900 p-3 text-xs text-slate-100">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </details>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              Submit the form to view the generated pack. Results will display here.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

function FlightSections({
  outbound,
  inbound,
}: {
  outbound: FlightOptionResponse[];
  inbound: FlightOptionResponse[];
}) {
  if (!outbound.length && !inbound.length) return null;
  return (
    <div>
      <h3 className="font-medium">Flight Options</h3>
      <div className="mt-2 grid gap-4 md:grid-cols-2">
        <FlightColumn title="Outbound (departing home)" flights={outbound} />
        <FlightColumn title="Inbound (returning home)" flights={inbound} />
      </div>
    </div>
  );
}

function FlightColumn({ title, flights }: { title: string; flights: FlightOptionResponse[] }) {
  return (
    <div className="rounded border border-slate-200 bg-white p-3 shadow-sm text-sm">
      <p className="text-xs font-semibold uppercase text-slate-500">{title}</p>
      <div className="mt-2 space-y-2 max-h-72 overflow-y-auto pr-1">
        {flights.length === 0 ? (
          <p className="text-xs text-slate-500">No options returned.</p>
        ) : (
          flights.map((flight, idx) => (
            <div key={`${title}-${idx}-${flight.booking_url}`} className="rounded border border-slate-200 p-3">
              <div className="font-semibold">{flight.airline}</div>
              <p className="text-slate-600">Depart: {formatDateDisplay(flight.departure_time)}</p>
              <p className="text-slate-600">Arrive: {formatDateDisplay(flight.arrival_time)}</p>
              <p className="text-slate-600">Approx €{flight.price_eur.toFixed(0)}</p>
              <a className="text-sm text-blue-600" href={flight.booking_url} target="_blank" rel="noreferrer">
                View booking
              </a>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
