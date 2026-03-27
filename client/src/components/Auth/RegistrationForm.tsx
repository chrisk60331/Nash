import { useForm } from 'react-hook-form';
import React, { useContext, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Turnstile } from '@marsidev/react-turnstile';
import { ThemeContext, Spinner, Button, isDark } from '@librechat/client';
import { useRegisterUserMutation } from 'librechat-data-provider/react-query';
import type { TRegisterUser, TError, TStartupConfig } from 'librechat-data-provider';
import { useLocalize, TranslationKeys } from '~/hooks';
import { ErrorMessage } from './ErrorMessage';

interface RegistrationFormProps {
  startupConfig: TStartupConfig;
  onSuccess?: () => void;
}

const RegistrationForm: React.FC<RegistrationFormProps> = ({ startupConfig, onSuccess }) => {
  const navigate = useNavigate();
  const localize = useLocalize();
  const { theme } = useContext(ThemeContext);

  const {
    watch,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<TRegisterUser>({ mode: 'onChange' });
  const password = watch('password');

  const [errorMessage, setErrorMessage] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [countdown, setCountdown] = useState<number>(3);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [termsChecked, setTermsChecked] = useState(false);

  const validTheme = isDark(theme) ? 'dark' : 'light';
  const requireCaptcha = Boolean(startupConfig?.turnstile?.siteKey);

  const registerUser = useRegisterUserMutation({
    onMutate: () => {
      setIsSubmitting(true);
    },
    onSuccess: () => {
      setIsSubmitting(false);
      setCountdown(3);
      onSuccess?.();
      const timer = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(timer);
            navigate('/c/new', { replace: true });
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    },
    onError: (error: unknown) => {
      setIsSubmitting(false);
      if ((error as TError).response?.data?.message) {
        setErrorMessage((error as TError).response?.data?.message ?? '');
      }
    },
  });

  const renderInput = (id: string, label: TranslationKeys, type: string, validation: object) => (
    <div className="mb-4">
      <div className="relative">
        <input
          id={`modal-reg-${id}`}
          type={type}
          autoComplete={id}
          aria-label={localize(label)}
          {...register(
            id as 'name' | 'email' | 'username' | 'password' | 'confirm_password',
            validation,
          )}
          aria-invalid={!!errors[id]}
          className="webkit-dark-styles transition-color peer w-full rounded-2xl border border-border-light bg-surface-primary px-3.5 pb-2.5 pt-3 text-text-primary duration-200 focus:border-green-500 focus:outline-none"
          placeholder=" "
          data-testid={id}
        />
        <label
          htmlFor={`modal-reg-${id}`}
          className="absolute start-3 top-1.5 z-10 origin-[0] -translate-y-4 scale-75 transform bg-surface-primary px-2 text-sm text-text-secondary-alt duration-200 peer-placeholder-shown:top-1/2 peer-placeholder-shown:-translate-y-1/2 peer-placeholder-shown:scale-100 peer-focus:top-1.5 peer-focus:-translate-y-4 peer-focus:scale-75 peer-focus:px-2 peer-focus:text-green-500 rtl:peer-focus:left-auto rtl:peer-focus:translate-x-1/4"
        >
          {localize(label)}
        </label>
      </div>
      {errors[id] && (
        <span role="alert" className="mt-1 text-sm text-red-500">
          {String(errors[id]?.message) ?? ''}
        </span>
      )}
    </div>
  );

  return (
    <>
      {errorMessage && (
        <ErrorMessage>
          {localize('com_auth_error_create')} {errorMessage}
        </ErrorMessage>
      )}
      {registerUser.isSuccess && countdown > 0 && (
        <div
          className="rounded-md border border-green-500 bg-green-500/10 px-3 py-2 text-sm text-gray-600 dark:text-gray-200"
          role="alert"
        >
          {localize(
            startupConfig?.emailEnabled
              ? 'com_auth_registration_success_generic'
              : 'com_auth_registration_success_insecure',
          ) +
            ' ' +
            localize('com_auth_email_verification_redirecting', { 0: countdown.toString() })}
        </div>
      )}

      <form
        className="mt-2"
        aria-label="Registration form"
        method="POST"
        onSubmit={handleSubmit((data: TRegisterUser) =>
          registerUser.mutate({ ...data }),
        )}
      >
        {renderInput('name', 'com_auth_full_name', 'text', {
          required: localize('com_auth_name_required'),
          minLength: { value: 3, message: localize('com_auth_name_min_length') },
          maxLength: { value: 80, message: localize('com_auth_name_max_length') },
        })}
        {renderInput('username', 'com_auth_username', 'text', {
          minLength: { value: 2, message: localize('com_auth_username_min_length') },
          maxLength: { value: 80, message: localize('com_auth_username_max_length') },
        })}
        {renderInput('email', 'com_auth_email', 'email', {
          required: localize('com_auth_email_required'),
          minLength: { value: 1, message: localize('com_auth_email_min_length') },
          maxLength: { value: 120, message: localize('com_auth_email_max_length') },
          pattern: { value: /\S+@\S+\.\S+/, message: localize('com_auth_email_pattern') },
        })}
        {renderInput('password', 'com_auth_password', 'password', {
          required: localize('com_auth_password_required'),
          minLength: {
            value: startupConfig?.minPasswordLength || 8,
            message: localize('com_auth_password_min_length'),
          },
          maxLength: { value: 128, message: localize('com_auth_password_max_length') },
        })}
        {renderInput('confirm_password', 'com_auth_password_confirm', 'password', {
          validate: (value: string) =>
            value === password || localize('com_auth_password_not_match'),
        })}

        {startupConfig?.turnstile?.siteKey && (
          <div className="my-4 flex justify-center">
            <Turnstile
              siteKey={startupConfig.turnstile.siteKey}
              options={{ ...startupConfig.turnstile.options, theme: validTheme }}
              onSuccess={(token) => setTurnstileToken(token)}
              onError={() => setTurnstileToken(null)}
              onExpire={() => setTurnstileToken(null)}
            />
          </div>
        )}

        <label className="mb-4 flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={termsChecked}
            onChange={(e) => setTermsChecked(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 rounded border-border-light accent-green-600"
            aria-required="true"
          />
          <span className="text-xs text-gray-600 dark:text-gray-400">
            I agree to Nash&apos;s{' '}
            <Link
              to="/terms"
              target="_blank"
              className="text-green-600 hover:underline dark:text-green-400"
            >
              Terms of Service
            </Link>{' '}
            and{' '}
            <Link
              to="/privacy"
              target="_blank"
              className="text-green-600 hover:underline dark:text-green-400"
            >
              Privacy Policy
            </Link>
          </span>
        </label>

        <div className="mt-2">
          <Button
            disabled={
              Object.keys(errors).length > 0 ||
              isSubmitting ||
              !termsChecked ||
              (requireCaptcha && !turnstileToken)
            }
            type="submit"
            aria-label="Submit registration"
            variant="submit"
            className="h-12 w-full rounded-2xl"
          >
            {isSubmitting ? <Spinner /> : localize('com_auth_continue')}
          </Button>
        </div>
      </form>
    </>
  );
};

export default RegistrationForm;
