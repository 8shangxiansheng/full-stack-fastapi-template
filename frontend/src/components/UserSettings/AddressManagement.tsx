import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { useState } from "react"

import { type AddressesReadAddressesResponse, AddressesService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

type AddressFormState = {
  receiver_name: string
  receiver_phone: string
  province: string
  city: string
  district: string
  detail: string
  is_default: boolean
}

const defaultForm: AddressFormState = {
  receiver_name: "",
  receiver_phone: "",
  province: "",
  city: "",
  district: "",
  detail: "",
  is_default: false,
}

function getAddressQueryOptions() {
  return {
    queryFn: (): Promise<AddressesReadAddressesResponse> =>
      AddressesService.readAddresses(),
    queryKey: ["addresses"],
  }
}

function AddressManagement() {
  const [form, setForm] = useState<AddressFormState>(defaultForm)
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()

  const { data: addresses } = useSuspenseQuery(getAddressQueryOptions())

  const createMutation = useMutation({
    mutationFn: () =>
      AddressesService.createAddress({
        requestBody: form,
      }),
    onSuccess: () => {
      showSuccessToast("Address created")
      setForm(defaultForm)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["addresses"] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (addressId: string) =>
      AddressesService.deleteAddress({ addressId }),
    onSuccess: () => {
      showSuccessToast("Address deleted")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["addresses"] })
    },
  })

  const setDefaultMutation = useMutation({
    mutationFn: (addressId: string) =>
      AddressesService.updateAddress({
        addressId,
        requestBody: { is_default: true },
      }),
    onSuccess: () => {
      showSuccessToast("Default address updated")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["addresses"] })
    },
  })

  const isFormValid =
    form.receiver_name.trim() &&
    form.receiver_phone.trim() &&
    form.province.trim() &&
    form.city.trim() &&
    form.district.trim() &&
    form.detail.trim()

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h3 className="text-lg font-semibold py-2">Address Management</h3>
        <p className="text-sm text-muted-foreground">
          Manage your delivery addresses
        </p>
      </div>

      <div className="rounded-lg border p-4 space-y-3">
        <h4 className="font-medium">Add New Address</h4>
        <div className="grid gap-3 md:grid-cols-2">
          <Input
            placeholder="Receiver name"
            value={form.receiver_name}
            onChange={(event) =>
              setForm((prev) => ({
                ...prev,
                receiver_name: event.target.value,
              }))
            }
          />
          <Input
            placeholder="Receiver phone"
            value={form.receiver_phone}
            onChange={(event) =>
              setForm((prev) => ({
                ...prev,
                receiver_phone: event.target.value,
              }))
            }
          />
          <Input
            placeholder="Province"
            value={form.province}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, province: event.target.value }))
            }
          />
          <Input
            placeholder="City"
            value={form.city}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, city: event.target.value }))
            }
          />
          <Input
            placeholder="District"
            value={form.district}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, district: event.target.value }))
            }
          />
          <Input
            placeholder="Detail address"
            value={form.detail}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, detail: event.target.value }))
            }
          />
        </div>

        <div className="flex items-center gap-2">
          <Checkbox
            checked={form.is_default}
            onCheckedChange={(value) =>
              setForm((prev) => ({ ...prev, is_default: value === true }))
            }
            id="default-address"
          />
          <label
            htmlFor="default-address"
            className="text-sm text-muted-foreground"
          >
            Set as default address
          </label>
        </div>

        <LoadingButton
          loading={createMutation.isPending}
          disabled={!isFormValid}
          onClick={() => createMutation.mutate()}
        >
          Add Address
        </LoadingButton>
      </div>

      <div className="space-y-3">
        {addresses.length === 0 ? (
          <p className="text-sm text-muted-foreground">No addresses yet</p>
        ) : (
          addresses.map((address) => (
            <div
              key={address.id}
              className="flex items-center justify-between rounded-lg border p-4"
            >
              <div className="space-y-1">
                <p className="font-medium">
                  {address.receiver_name} · {address.receiver_phone}
                </p>
                <p className="text-sm text-muted-foreground">
                  {address.province} {address.city} {address.district}{" "}
                  {address.detail}
                </p>
                {address.is_default ? (
                  <p className="text-xs text-primary">Default address</p>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={setDefaultMutation.isPending || address.is_default}
                  onClick={() => setDefaultMutation.mutate(address.id)}
                >
                  Set Default
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate(address.id)}
                >
                  Delete
                </Button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default AddressManagement
