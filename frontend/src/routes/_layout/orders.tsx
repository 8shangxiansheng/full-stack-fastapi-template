import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Clock3 } from "lucide-react"
import { Suspense, useState } from "react"

import { type OrderStatus, OrdersService, PaymentsService } from "@/client"
import PendingItems from "@/components/Pending/PendingItems"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

type OrderStatusFilter = "all" | OrderStatus

function getOrdersQueryOptions(status: OrderStatusFilter) {
  return {
    queryFn: () => OrdersService.readOrders(status === "all" ? {} : { status }),
    queryKey: ["orders", status],
  }
}

function formatAmount(value: string | number) {
  const amount = typeof value === "string" ? Number(value) : value
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00"
}

type OrderAction = {
  event: string
  label: string
  variant: "default" | "outline" | "destructive" | "secondary"
}

function getOrderActions(status: string, isSuperuser: boolean): OrderAction[] {
  if (isSuperuser) {
    const merchantActions: Record<string, OrderAction[]> = {
      paid: [{ event: "merchant_accept", label: "Accept", variant: "default" }],
      accepted: [
        {
          event: "start_preparing",
          label: "Start Preparing",
          variant: "default",
        },
      ],
      preparing: [
        {
          event: "ready_for_delivery",
          label: "Ready For Delivery",
          variant: "default",
        },
      ],
      ready_for_delivery: [
        { event: "dispatch", label: "Dispatch", variant: "default" },
      ],
      delivering: [
        { event: "complete", label: "Complete", variant: "default" },
      ],
      refund_pending: [
        {
          event: "approve_refund",
          label: "Approve Refund",
          variant: "secondary",
        },
        {
          event: "reject_refund",
          label: "Reject Refund",
          variant: "destructive",
        },
      ],
      pending_payment: [
        { event: "cancel", label: "Cancel", variant: "destructive" },
      ],
    }
    return merchantActions[status] ?? []
  }

  if (status === "pending_payment") {
    return [{ event: "cancel", label: "Cancel", variant: "destructive" }]
  }
  if (
    [
      "paid",
      "accepted",
      "preparing",
      "ready_for_delivery",
      "delivering",
      "completed",
    ].includes(status)
  ) {
    return [
      { event: "request_refund", label: "Request Refund", variant: "outline" },
    ]
  }
  return []
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
  const { user: currentUser } = useAuth()
  const [statusFilter, setStatusFilter] = useState<OrderStatusFilter>("all")
  const { data: orders } = useSuspenseQuery(getOrdersQueryOptions(statusFilter))

  const payMutation = useMutation({
    mutationFn: async (orderId: string) => {
      const payment = await PaymentsService.createPayment({
        requestBody: { order_id: orderId, provider: "mockpay" },
      })
      await PaymentsService.paymentCallback({
        requestBody: {
          provider: "mockpay",
          transaction_id: payment.out_trade_no,
          payload: JSON.stringify({
            out_trade_no: payment.out_trade_no,
            status: "success",
          }),
        },
      })
    },
    onSuccess: () => {
      showSuccessToast("Payment completed")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["orders"] })
    },
  })

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
      <div className="flex justify-end">
        <Select
          value={statusFilter}
          onValueChange={(value) => setStatusFilter(value as OrderStatusFilter)}
        >
          <SelectTrigger className="w-full md:w-56">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="pending_payment">Pending Payment</SelectItem>
            <SelectItem value="paid">Paid</SelectItem>
            <SelectItem value="accepted">Accepted</SelectItem>
            <SelectItem value="preparing">Preparing</SelectItem>
            <SelectItem value="ready_for_delivery">
              Ready For Delivery
            </SelectItem>
            <SelectItem value="delivering">Delivering</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
            <SelectItem value="refund_pending">Refund Pending</SelectItem>
            <SelectItem value="refunded">Refunded</SelectItem>
            <SelectItem value="refund_rejected">Refund Rejected</SelectItem>
          </SelectContent>
        </Select>
      </div>
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
          <div className="flex flex-wrap gap-2">
            {!currentUser?.is_superuser &&
              order.status === "pending_payment" && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={payMutation.isPending || statusMutation.isPending}
                  onClick={() => payMutation.mutate(order.id)}
                >
                  Pay
                </Button>
              )}
            {getOrderActions(
              order.status,
              currentUser?.is_superuser ?? false,
            ).map((action) => (
              <Button
                key={`${order.id}-${action.event}`}
                variant={action.variant}
                size="sm"
                disabled={statusMutation.isPending || payMutation.isPending}
                onClick={() =>
                  statusMutation.mutate({
                    orderId: order.id,
                    event: action.event,
                  })
                }
              >
                {action.label}
              </Button>
            ))}
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
