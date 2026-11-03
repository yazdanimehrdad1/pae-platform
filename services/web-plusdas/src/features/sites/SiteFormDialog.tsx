import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { SiteRecord, SiteCreateRequest, SiteProfileInfo } from "@/api/types/sites";
import { BROWSER_TIME_ZONE } from "@/shared/hooks/useDisplayTimeZone";
import { FieldLabel, FieldMarkerLegend } from "./components/FieldLabel";
import { TimeZoneCombobox } from "./components/TimeZoneCombobox";
import { isTimeZone } from "./lib/timeZones";

const formSchema = z.object({
  client_id: z.string().min(1, "Required"),
  name: z.string().min(1, "Required"),
  operator: z.string().min(1, "Required"),
  capacity: z.string().min(1, "Required"),
  description: z.string(),
  street: z.string().min(1, "Required"),
  city: z.string().min(1, "Required"),
  state: z.string().min(1, "Required"),
  zip_code: z.coerce.number().int(),
  // Coordinates are optional (nullable in the contract): both blank means none.
  lat: z.string(),
  lng: z.string(),
  // Optional, meters above sea level; the PV forecast uses it for solar position.
  elevation_m: z.string(),
  // The site's local time: its reports' days and schedules, and how its times are shown.
  timezone: z.string().trim().min(1, "Required").refine(isTimeZone, "Choose a time zone from the list"),
  // The site's code in backend-ot (its functions, alarms, virtual points); NO_PROFILE for none.
  profile: z.string(),
}).superRefine((values, ctx) => {
  if (values.lat.trim() === "" && values.lng.trim() === "") {
    if (values.elevation_m.trim() !== "") {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["elevation_m"], message: "Needs latitude and longitude" });
    }
    return;
  }
  for (const field of ["lat", "lng"] as const) {
    if (values[field].trim() === "" || Number.isNaN(Number(values[field]))) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: [field], message: "Enter a number, or leave both blank" });
    }
  }
  const elevation = values.elevation_m.trim();
  if (elevation !== "" && (Number.isNaN(Number(elevation)) || Number(elevation) < -500 || Number(elevation) > 9000)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["elevation_m"], message: "Enter -500 to 9000, or leave blank" });
  }
});

type FormValues = z.infer<typeof formSchema>;

// The select's value for "no profile" (a Select item can't have an empty value).
const NO_PROFILE = "none";

const emptyValues: FormValues = {
  client_id: "",
  name: "",
  operator: "",
  capacity: "",
  description: "",
  street: "",
  city: "",
  state: "",
  zip_code: 0,
  lat: "",
  lng: "",
  elevation_m: "",
  timezone: BROWSER_TIME_ZONE,
  profile: NO_PROFILE,
};

function fromSite(site: SiteRecord): FormValues {
  return {
    client_id: site.client_id,
    name: site.name,
    operator: site.operator,
    capacity: site.capacity,
    description: site.description ?? "",
    street: site.location?.street ?? "",
    city: site.location?.city ?? "",
    state: site.location?.state ?? "",
    zip_code: site.location?.zip_code ?? 0,
    lat: site.coordinates ? String(site.coordinates.lat) : "",
    lng: site.coordinates ? String(site.coordinates.lng) : "",
    elevation_m: site.coordinates?.elevation_m != null ? String(site.coordinates.elevation_m) : "",
    timezone: site.timezone,
    profile: site.profile ?? NO_PROFILE,
  };
}

function toRequest(values: FormValues): SiteCreateRequest {
  return {
    client_id: values.client_id,
    name: values.name,
    operator: values.operator,
    capacity: values.capacity,
    description: values.description,
    location: { street: values.street, city: values.city, state: values.state, zip_code: values.zip_code },
    coordinates: values.lat.trim() === ""
      ? null
      : {
        lat: Number(values.lat),
        lng: Number(values.lng),
        ...(values.elevation_m.trim() !== "" ? { elevation_m: Number(values.elevation_m) } : {}),
      },
    timezone: values.timezone.trim(),
    profile: values.profile === NO_PROFILE ? null : values.profile,
  };
}

export function SiteFormDialog({ open, onOpenChange, site, profiles, onSubmit }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  site?: SiteRecord;
  /** The registered profiles; one held by another site is shown but can't be chosen. */
  profiles: SiteProfileInfo[];
  onSubmit: (payload: SiteCreateRequest) => Promise<void>;
}) {
  // The site's own profile stays listed even before the profiles have loaded.
  const profileOptions = site?.profile && !profiles.some(profile => profile.key === site.profile)
    ? [{ key: site.profile, site_id: site.site_id }, ...profiles]
    : profiles;
  const { register, control, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    values: site ? fromSite(site) : emptyValues,
  });

  const onValid = async (values: FormValues) => {
    try {
      await onSubmit(toRequest(values));
      reset();
      onOpenChange(false);
    } catch {
      // error is reported to the user by the caller's mutation
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{site ? "Edit Site" : "Add Site"}</DialogTitle>
          <FieldMarkerLegend markers={["required", "recommended"]} />
        </DialogHeader>
        <form onSubmit={handleSubmit(onValid)} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <FieldLabel htmlFor="client_id" marker="required">Client ID</FieldLabel>
              <Input id="client_id" {...register("client_id")} />
              {errors.client_id && <p className="text-xs text-destructive">{errors.client_id.message}</p>}
            </div>
            <div className="space-y-1">
              <FieldLabel htmlFor="name" marker="required">Name</FieldLabel>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <FieldLabel htmlFor="operator" marker="required">Operator</FieldLabel>
              <Input id="operator" {...register("operator")} />
              {errors.operator && <p className="text-xs text-destructive">{errors.operator.message}</p>}
            </div>
            <div className="space-y-1">
              <FieldLabel htmlFor="capacity" marker="required">Capacity</FieldLabel>
              <Input id="capacity" placeholder="e.g. 100kW" {...register("capacity")} />
              {errors.capacity && <p className="text-xs text-destructive">{errors.capacity.message}</p>}
            </div>
          </div>

          <div className="space-y-1">
            <FieldLabel htmlFor="timezone" marker="required">Time zone</FieldLabel>
            <Controller control={control} name="timezone" render={({ field }) => (
              <TimeZoneCombobox id="timezone" value={field.value} onChange={field.onChange} invalid={Boolean(errors.timezone)} />
            )} />
            <p className="text-xs text-muted-foreground">Where the site is: its reports use this zone's days, and its times are shown in it.</p>
            {errors.timezone && <p className="text-xs text-destructive">{errors.timezone.message}</p>}
          </div>

          <div className="space-y-1">
            <FieldLabel htmlFor="profile" marker="recommended">Site profile</FieldLabel>
            <Controller control={control} name="profile" render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="profile"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_PROFILE}>None</SelectItem>
                  {profileOptions.map(profile => {
                    const heldElsewhere = profile.site_id !== null && profile.site_id !== site?.site_id;
                    return (
                      <SelectItem key={profile.key} value={profile.key} disabled={heldElsewhere}>
                        {profile.key}{heldElsewhere ? ` (used by site ${profile.site_id})` : ""}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            )} />
            <p className="text-xs text-muted-foreground">The site's own code: its site functions, profile alarms and virtual points.</p>
          </div>

          <div className="space-y-1">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" {...register("description")} />
          </div>

          <div className="space-y-1">
            <FieldLabel htmlFor="street" marker="required">Street</FieldLabel>
            <Input id="street" {...register("street")} />
            {errors.street && <p className="text-xs text-destructive">{errors.street.message}</p>}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-1">
              <FieldLabel htmlFor="city" marker="required">City</FieldLabel>
              <Input id="city" {...register("city")} />
              {errors.city && <p className="text-xs text-destructive">{errors.city.message}</p>}
            </div>
            <div className="space-y-1">
              <FieldLabel htmlFor="state" marker="required">State</FieldLabel>
              <Input id="state" {...register("state")} />
              {errors.state && <p className="text-xs text-destructive">{errors.state.message}</p>}
            </div>
            <div className="space-y-1">
              <FieldLabel htmlFor="zip_code" marker="required">Zip Code</FieldLabel>
              <Input id="zip_code" type="number" {...register("zip_code")} />
              {errors.zip_code && <p className="text-xs text-destructive">{errors.zip_code.message}</p>}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-1">
              <FieldLabel htmlFor="lat" marker="recommended">Latitude</FieldLabel>
              <Input id="lat" type="number" step="any" {...register("lat")} />
              {errors.lat && <p className="text-xs text-destructive">{errors.lat.message}</p>}
            </div>
            <div className="space-y-1">
              <FieldLabel htmlFor="lng" marker="recommended">Longitude</FieldLabel>
              <Input id="lng" type="number" step="any" {...register("lng")} />
              {errors.lng && <p className="text-xs text-destructive">{errors.lng.message}</p>}
            </div>
            <div className="space-y-1">
              <FieldLabel htmlFor="elevation_m" marker="recommended">Elevation (m)</FieldLabel>
              <Input id="elevation_m" type="number" step="any" {...register("elevation_m")} />
              {errors.elevation_m && <p className="text-xs text-destructive">{errors.elevation_m.message}</p>}
            </div>
            <p className="text-xs text-muted-foreground sm:col-span-3">The PV forecast needs the site's location (and uses its elevation).</p>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving..." : "Save"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
