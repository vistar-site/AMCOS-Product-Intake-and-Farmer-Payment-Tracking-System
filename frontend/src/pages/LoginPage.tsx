import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Sprout } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { loginSchema, type LoginValues } from "../features/auth/schemas";
import { Alert, Button, Field, Input } from "../components/ui";

export default function LoginPage() {
  const { login, status } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [showPw, setShowPw] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  if (status === "authenticated") return <Navigate to="/" replace />;

  const onSubmit = async (v: LoginValues) => {
    setServerError(null);
    try {
      await login(v.email, v.password);
      navigate((location.state as { from?: string })?.from ?? "/", {
        replace: true,
      });
    } catch (e) {
      setServerError((e as Error).message);
    }
  };

  return (
    <div className="flex min-h-screen">
      <div className="hidden flex-1 flex-col justify-between bg-brand-900 p-10 text-white lg:flex">
        <div className="flex items-center gap-2">
          <span className="grid size-9 place-items-center rounded-md bg-brand-500">
            <Sprout className="size-5" />
          </span>
          <span className="font-semibold">AMCOS Produce &amp; Payments</span>
        </div>
        <div className="max-w-md">
          <h2 className="text-3xl font-semibold leading-tight">
            Every kilogram recorded. Every shilling accounted for.
          </h2>
          <p className="mt-3 text-brand-100/80">
            Produce intake, warehouse reconciliation, auction results and farmer
            payments in one traceable system.
          </p>
          <p className="text-brand-100/80 mt-6 text-sm">
            Demo credentials: <br />
            <span className="font-semibold">
              manager@demo.amcos.test
            </span> / <span className="font-semibold">Demo2026pass</span>
            <br />
            <span className="font-semibold">
              manager2@demo.amcos.test
            </span> / <span className="font-semibold">Demo2026pass</span>
            <br />
            <span className="font-semibold">clerk1@demo.amcos.test</span> /{" "}
            <span className="font-semibold">Demo2026pass</span>
            <br />
            <span className="font-semibold">clerk2@demo.amcos.test</span> /{" "}
            <span className="font-semibold">Demo2026pass</span>
            <br />
            <span className="font-semibold">
              accountant@demo.amcos.test
            </span> / <span className="font-semibold">Demo2026pass</span>
            <br />
            <span className="font-semibold">
              warehouse@demo.amcos.test
            </span> / <span className="font-semibold">Demo2026pass</span>
            <br />
            <span className="font-semibold">
              auditor@demo.amcos.test
            </span> / <span className="font-semibold">Demo2026pass</span>
          </p>
        </div>
        <p className="text-xs text-brand-100/50">
          Authorized cooperative staff only. All activity is audited.
        </p>
      </div>

      <div className="flex flex-1 items-center justify-center px-4 py-12">
        <form
          onSubmit={handleSubmit(onSubmit)}
          noValidate
          className="w-full max-w-sm space-y-5"
        >
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
            <p className="mt-1 text-sm text-slate-500">
              Use the account provided by your AMCOS administrator.
            </p>
          </div>
          {serverError && <Alert>{serverError}</Alert>}
          <Field label="Email" htmlFor="email" error={errors.email?.message}>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              autoFocus
              invalid={!!errors.email}
              {...register("email")}
            />
          </Field>
          <Field
            label="Password"
            htmlFor="password"
            error={errors.password?.message}
          >
            <div className="relative">
              <Input
                id="password"
                type={showPw ? "text" : "password"}
                autoComplete="current-password"
                invalid={!!errors.password}
                className="pr-10"
                {...register("password")}
              />
              <button
                type="button"
                onClick={() => setShowPw((s) => !s)}
                className="absolute inset-y-0 right-0 px-3 text-slate-500"
                aria-label={showPw ? "Hide password" : "Show password"}
              >
                {showPw ? (
                  <EyeOff className="size-4" />
                ) : (
                  <Eye className="size-4" />
                )}
              </button>
            </div>
          </Field>
          <Button type="submit" className="w-full" loading={isSubmitting}>
            Sign in
          </Button>
        </form>
      </div>
    </div>
  );
}
