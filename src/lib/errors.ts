export class AppError extends Error {
  constructor(
    message: string,
    public status: number = 400,
    public code?: string,
  ) {
    super(message);
    this.name = "AppError";
  }
}

export function toErrorResponse(error: unknown): Response {
  if (error instanceof AppError) {
    return Response.json(
      { error: error.message, code: error.code },
      { status: error.status },
    );
  }

  console.error(error);
  return Response.json(
    { error: "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin." },
    { status: 500 },
  );
}
