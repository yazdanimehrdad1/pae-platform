import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import type { SiteRecord, SiteCreateRequest } from "@/shared/types/site";

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
  lat: z.coerce.number(),
  lng: z.coerce.number(),
});

type FormValues = z.infer<typeof formSchema>;

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
  lat: 0,
  lng: 0,
};

function fromSite(site: SiteRecord): FormValues {
  return {
    client_id: site.client_id,
    name: site.name,
    operator: site.operator,
    capacity: site.capacity,
    description: site.description,
    street: site.location.street,
    city: site.location.city,
    state: site.location.state,
    zip_code: site.location.zip_code,
    lat: site.coordinates.lat,
    lng: site.coordinates.lng,
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
    coordinates: { lat: values.lat, lng: values.lng },
  };
}

export function SiteFormDialog({ open, onOpenChange, site, onSubmit }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  site?: SiteRecord;
  onSubmit: (payload: SiteCreateRequest) => Promise<void>;
}) {
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormValues>({
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
        </DialogHeader>
        <form onSubmit={handleSubmit(onValid)} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="client_id">Client ID</Label>
              <Input id="client_id" {...register("client_id")} />
              {errors.client_id && <p className="text-xs text-destructive">{errors.client_id.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="operator">Operator</Label>
              <Input id="operator" {...register("operator")} />
              {errors.operator && <p className="text-xs text-destructive">{errors.operator.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="capacity">Capacity</Label>
              <Input id="capacity" placeholder="e.g. 100kW" {...register("capacity")} />
              {errors.capacity && <p className="text-xs text-destructive">{errors.capacity.message}</p>}
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" {...register("description")} />
          </div>

          <div className="space-y-1">
            <Label htmlFor="street">Street</Label>
            <Input id="street" {...register("street")} />
            {errors.street && <p className="text-xs text-destructive">{errors.street.message}</p>}
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label htmlFor="city">City</Label>
              <Input id="city" {...register("city")} />
              {errors.city && <p className="text-xs text-destructive">{errors.city.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="state">State</Label>
              <Input id="state" {...register("state")} />
              {errors.state && <p className="text-xs text-destructive">{errors.state.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="zip_code">Zip Code</Label>
              <Input id="zip_code" type="number" {...register("zip_code")} />
              {errors.zip_code && <p className="text-xs text-destructive">{errors.zip_code.message}</p>}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="lat">Latitude</Label>
              <Input id="lat" type="number" step="any" {...register("lat")} />
              {errors.lat && <p className="text-xs text-destructive">{errors.lat.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="lng">Longitude</Label>
              <Input id="lng" type="number" step="any" {...register("lng")} />
              {errors.lng && <p className="text-xs text-destructive">{errors.lng.message}</p>}
            </div>
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
