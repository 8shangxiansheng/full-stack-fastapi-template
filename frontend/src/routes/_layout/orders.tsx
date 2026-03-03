import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Clock3 } from "lucide-react"
import { Suspense } from "react"

import { OrdersService } from "@/client"
import PendingItems from "@/components/Pending/PendingItems"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

function getOrdersQueryOptions() {
  return {
    queryFn: () => OrdersService.readOrders(),
    queryKey: ["orders"],
  }
}

function formatAmount(value: string | number) {
  const amount = typeof value === "string" ? Number(value) : value
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00"
}

export const Route = createFileRoute("/_layout/orders")({
  component: OrdersPage,
  head: () => ({
    meta: [
      {
        title: "Orders - FastAPI Template",
      },
    ],
  }),
})

function OrdersContent() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const { data: orders } = useSuspenseQuery(getOrdersQueryOptions())

  const statusMutation = useMutation({
    mutationFn: ({ orderId, event }: { orderId: string; event: string }) =>
      OrdersService.changeOrderStatus({
        orderId,
        requestBody: { event },
      }),
    onSuccess: () => {
      showSuccessToast("Order status updated")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["orders"] })
    },
  })

  if (orders.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Clock3 className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No orders yet</h3>
        <p className="text-muted-foreground">
          Create your first order from cart
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {orders.map((order) => (
        <div key={order.id} className="rounded-lg border p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              <p className="font-medium">{order.order_no}</p>
              <p className="text-sm text-muted-foreground">
                Total: ¥ {formatAmount(order.total_amount)}
              </p>
            </div>
            <Badge variant="secondary">{order.status}</Badge>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={
                statusMutation.isPending || order.status !== "pending_payment"
              }
              onClick={() =>
                statusMutation.mutate({ orderId: order.id, event: "pay" })
              }
            >
              Pay
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={
                statusMutation.isPending || order.status !== "pending_payment"
              }
              onClick={() =>
                statusMutation.mutate({
                  orderId: order.id,
                  event: "cancel",
                })
              }
            >
              Cancel
            </Button>
          </div>
        </div>
      ))}
    </div>
  )
}

function OrdersTable() {
  return (
    <Suspense fallback={<PendingItems />}>
      <OrdersContent />
    </Suspense>
  )
}

function OrdersPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Orders</h1>
        <p className="text-muted-foreground">Track your placed orders</p>
      </div>
      <OrdersTable />
    </div>
  )
}
