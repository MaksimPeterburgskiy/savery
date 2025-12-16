/**
 * Geographic utility functions for distance calculations.
 */

/** Earth's radius in meters */
const EARTH_RADIUS_M = 6_371_000;

/** Meters per mile conversion factor */
const METERS_PER_MILE = 1_609.344;

/** Meters per kilometer conversion factor */
const METERS_PER_KM = 1_000;

/**
 * Coordinates represented as latitude and longitude.
 */
export interface Coordinates {
  latitude: number;
  longitude: number;
}

/**
 * Converts degrees to radians.
 */
function toRadians(degrees: number): number {
  return degrees * (Math.PI / 180);
}

/**
 * Calculates the great-circle distance between two points on Earth
 * using the Haversine formula.
 *
 * @param from - The starting coordinates
 * @param to - The destination coordinates
 * @returns Distance in meters
 *
 * @example
 * ```ts
 * const distance = haversineDistanceMeters(
 *   { latitude: 40.7128, longitude: -74.006 }, // NYC
 *   { latitude: 34.0522, longitude: -118.2437 } // LA
 * );
 * // ~3,944,422 meters
 * ```
 */
export function haversineDistanceMeters(from: Coordinates, to: Coordinates): number {
  const lat1Rad = toRadians(from.latitude);
  const lat2Rad = toRadians(to.latitude);
  const deltaLat = toRadians(to.latitude - from.latitude);
  const deltaLon = toRadians(to.longitude - from.longitude);

  const a =
    Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
    Math.cos(lat1Rad) * Math.cos(lat2Rad) * Math.sin(deltaLon / 2) * Math.sin(deltaLon / 2);

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return EARTH_RADIUS_M * c;
}

/**
 * Converts meters to miles.
 *
 * @param meters - Distance in meters
 * @returns Distance in miles
 *
 * @example
 * ```ts
 * metersToMiles(1609.344) // 1.0
 * ```
 */
export function metersToMiles(meters: number): number {
  return meters / METERS_PER_MILE;
}

/**
 * Converts meters to kilometers.
 *
 * @param meters - Distance in meters
 * @returns Distance in kilometers
 *
 * @example
 * ```ts
 * metersToKm(5000) // 5.0
 * ```
 */
export function metersToKm(meters: number): number {
  return meters / METERS_PER_KM;
}

/**
 * Converts miles to meters.
 *
 * @param miles - Distance in miles
 * @returns Distance in meters
 *
 * @example
 * ```ts
 * milesToMeters(1.0) // 1609.344
 * ```
 */
export function milesToMeters(miles: number): number {
  return miles * METERS_PER_MILE;
}

/**
 * Converts kilometers to meters.
 *
 * @param km - Distance in kilometers
 * @returns Distance in meters
 *
 * @example
 * ```ts
 * kmToMeters(5.0) // 5000
 * ```
 */
export function kmToMeters(km: number): number {
  return km * METERS_PER_KM;
}

/**
 * Formats a distance in meters to a human-readable string.
 * Uses miles if >= 0.1 mi, otherwise feet.
 *
 * @param meters - Distance in meters
 * @param options - Formatting options
 * @returns Formatted distance string
 *
 * @example
 * ```ts
 * formatDistance(1609) // "1.0 mi"
 * formatDistance(100) // "328 ft"
 * formatDistance(5000, { unit: 'metric' }) // "5.0 km"
 * ```
 */
export function formatDistance(
  meters: number,
  options: { unit?: 'imperial' | 'metric'; decimals?: number } = {}
): string {
  const { unit = 'imperial', decimals = 1 } = options;

  if (unit === 'metric') {
    if (meters >= 1000) {
      return `${metersToKm(meters).toFixed(decimals)} km`;
    }
    return `${Math.round(meters)} m`;
  }

  // Imperial
  const miles = metersToMiles(meters);
  if (miles >= 0.1) {
    return `${miles.toFixed(decimals)} mi`;
  }
  // Convert to feet (1 meter ≈ 3.28084 feet)
  const feet = meters * 3.28084;
  return `${Math.round(feet)} ft`;
}

/**
 * Calculates the distance between two points and returns it in miles.
 *
 * @param from - The starting coordinates
 * @param to - The destination coordinates
 * @returns Distance in miles
 *
 * @example
 * ```ts
 * const miles = distanceInMiles(
 *   { latitude: 40.7128, longitude: -74.006 },
 *   { latitude: 40.7580, longitude: -73.9855 }
 * );
 * // ~3.36 miles
 * ```
 */
export function distanceInMiles(from: Coordinates, to: Coordinates): number {
  return metersToMiles(haversineDistanceMeters(from, to));
}

/**
 * Calculates the distance between two points and returns it in kilometers.
 *
 * @param from - The starting coordinates
 * @param to - The destination coordinates
 * @returns Distance in kilometers
 */
export function distanceInKm(from: Coordinates, to: Coordinates): number {
  return metersToKm(haversineDistanceMeters(from, to));
}


