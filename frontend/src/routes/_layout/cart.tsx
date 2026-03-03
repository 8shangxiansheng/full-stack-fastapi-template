import {
  useMutation,
  useQuery,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { ShoppingCart, Trash2 } from "lucide-react"
import { Suspense, useMemo, useState } from "react"

import { AddressesService, CartService, OrdersService } from "@/client"
import PendingItems from "@/components/Pending/PendingItems"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

function getCartQueryOptions() {
  return {
    queryFn: () => CartService.readCart(),
    queryKey: ["cart"],
  }
}

function formatAmount(value: string | number) {
  const amount = typeof value === "string" ? Number(value) : value
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00"
}

export const Route = createFileRoute("/_layout/cart")({
  component: CartPage,
  head: () => ({
    meta: [
      {
        title: "Cart - FastAPI Template",
      },
    ],
  }),
})

function CartContent() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const navigate = useNavigate()
  const { data } = useSuspenseQuery(getCartQueryOptions())
  const { data: addresses = [] } = useQuery({
    queryFn: () => AddressesService.readAddresses(),
    queryKey: ["addresses"],
  })
  const [selectedAddressId, setSelectedAddressId] = useState<string>("")

  const defaultAddressId = useMemo(() => {
    if (selectedAddressId) {
      return selectedAddressId
    }
    const first =
      addresses.find((address) => address.is_default) ?? addresses[0]
    return first?.id ?? ""
  }, [addresses, selectedAddressId])

  const updateMutation = useMutation({
    mutationFn: ({
      cartItemId,
      quantity,
    }: {
      cartItemId: string
      quantity: number
    }) =>
      CartService.updateCartItem({
        cartItemId,
        requestBody: { quantity },
      }),
    onSuccess: () => {
      showSuccessToast("Cart item updated")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["cart"] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (cartItemId: string) =>
      CartService.deleteCartItem({ cartItemId }),
    onSuccess: () => {
      showSuccessToast("Cart item removed")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["cart"] })
    },
  })

  const clearMutation = useMutation({
    mutationFn: () => CartService.clearCart(),
    onSuccess: () => {
      showSuccessToast("Cart cleared")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["cart"] })
    },
  })

  const createOrderMutation = useMutation({
    mutationFn: (addressId: string) =>
      OrdersService.createOrder({
        requestBody: { address_id: addressId },
      }),
    onSuccess: () => {
      showSuccessToast("Order created")
      queryClient.invalidateQueries({ queryKey: ["cart"] })
      queryClient.invalidateQueries({ queryKey: ["orders"] })
      void navigate({ to: "/orders" })
    },
    onError: handleError.bind(showErrorToast),
  })

  if (data.items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ShoppingCart className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">Your cart is empty</h3>
        <p className="text-muted-foreground">Go to menu and add some dishes</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {data.items.map((item) => (
        <div
          key={item.id}
          className="flex items-center justify-between rounded-lg border p-4"
        >
          <div className="space-y-1">
            <p className="font-medium">{item.dish_name}</p>
            <p className="text-sm text-muted-foreground">{item.sku_name}</p>
            <p className="text-sm text-muted-foreground">
              ¥ {formatAmount(item.unit_price)} x {item.quantity} = ¥{" "}
              {formatAmount(item.line_amount)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={updateMutation.isPending || item.quantity <= 1}
              onClick={() =>
                updateMutation.mutate({
                  cartItemId: item.id,
                  quantity: item.quantity - 1,
                })
              }
            >
              -
            </Button>
            <span className="w-8 text-center text-sm">{item.quantity}</span>
            <Button
              variant="outline"
              size="sm"
              disabled={updateMutation.isPending || item.quantity >= item.stock}
              onClick={() =>
                updateMutation.mutate({
                  cartItemId: item.id,
                  quantity: item.quantity + 1,
                })
              }
            >
              +
            </Button>
            <Button
              variant="destructive"
              size="icon"
              disabled={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate(item.id)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ))}

      <div className="flex items-center justify-between rounded-lg border bg-muted/30 p-4">
        <div className="space-y-3 w-full">
          <div className="flex items-center justify-between gap-3">
            <p className="text-lg font-semibold">
              Total: ¥ {formatAmount(data.total_amount)}
            </p>
            <Button
              variant="outline"
              disabled={clearMutation.isPending}
              onClick={() => clearMutation.mutate()}
            >
              Clear Cart
            </Button>
          </div>
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <Select
              value={defaultAddressId}
              onValueChange={setSelectedAddressId}
              disabled={addresses.length === 0 || createOrderMutation.isPending}
            >
              <SelectTrigger className="w-full md:w-96">
                <SelectValue placeholder="Select delivery address" />
              </SelectTrigger>
              <SelectContent>
                {addresses.map((address) => (
                  <SelectItem key={address.id} value={address.id}>
                    {`${address.receiver_name} ${address.receiver_phone} | ${address.province}${address.city}${address.district}${address.detail}${address.is_default ? " (Default)" : ""}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {addresses.length === 0 ? (
              <Button asChild>
                <Link to="/settings">Create Address First</Link>
              </Button>
            ) : (
              <Button
                disabled={createOrderMutation.isPending || !defaultAddressId}
                onClick={() => createOrderMutation.mutate(defaultAddressId)}
              >
                Place Order
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function CartTable() {
  return (
    <Suspense fallback={<PendingItems />}>
      <CartContent />
    </Suspense>
  )
}

function CartPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Cart</h1>
        <p className="text-muted-foreground">
          Review your selected dishes before checkout
        </p>
      </div>
      <CartTable />
    </div>
  )
}
