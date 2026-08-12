export interface SystemHealth {
  online: boolean;
  status: string;
  server_name: string | null;
  message: string;
  target: string;
  grpc_code?: string;
}
