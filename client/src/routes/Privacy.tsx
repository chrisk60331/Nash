import LegalLayout from './LegalLayout';

export default function Privacy() {
  return (
    <LegalLayout title="Privacy Policy" lastUpdated="March 8, 2026">
      <p>
        Backboard.io, Inc. ("we", "us", or "our") operates Nash, an AI-powered chat platform
        available at nash.backboard.io ("Service"). This Privacy Policy explains how we collect,
        use, and protect your information when you use our Service.
      </p>

      <h2>1. Information We Collect</h2>

      <h3>Account Information</h3>
      <p>
        When you register, we collect your name, email address, and a hashed version of your
        password. If you sign in with Google, we receive your name, email, and profile picture
        from Google.
      </p>

      <h3>Conversation Data</h3>
      <p>
        We store the messages and files you submit to the Service so that your conversation
        history is available across sessions. This content is associated with your account and
        retained until you delete it or close your account.
      </p>

      <h3>Usage Data</h3>
      <p>
        We collect token usage counts, model selections, and feature interactions to power our
        billing system and improve the Service. We do not link this data to conversation content.
      </p>

      <h3>Payment Information</h3>
      <p>
        Subscription billing is handled by Stripe. We store only your Stripe customer ID and
        subscription status — no card numbers or payment details ever reach our servers.
      </p>

      <h3>Cookies and Session Data</h3>
      <p>
        We use cookies strictly for authentication (keeping you logged in) and security. See our{' '}
        <a href="/cookies">Cookie Policy</a> for details.
      </p>

      <h2>2. How We Use Your Information</h2>
      <ul>
        <li>To provide and operate the Service</li>
        <li>To authenticate you and maintain your session</li>
        <li>To process subscription payments and track usage against your plan</li>
        <li>To send you important service notifications (billing, security, policy changes)</li>
        <li>To detect and prevent abuse, fraud, and security incidents</li>
        <li>To improve the Service based on aggregate, non-personal usage patterns</li>
      </ul>
      <p>
        We do not sell your personal data. We do not use your conversation content to train AI
        models.
      </p>

      <h2>3. How We Share Your Information</h2>
      <p>We share your data only with the following categories of service providers:</p>
      <ul>
        <li>
          <strong>Backboard.io</strong> — our primary data storage platform. Your account data,
          conversation history, and user-generated content are stored in Backboard.
        </li>
        <li>
          <strong>Stripe</strong> — payment processing. Stripe is PCI-DSS compliant.
        </li>
        <li>
          <strong>AI Model Providers</strong> — when you send a message, it is forwarded to the
          AI provider associated with your selected model (e.g., OpenAI, Anthropic, Google,
          Cohere, AWS). These providers process your message content to generate a response.
          Each provider has their own privacy policy.
        </li>
        <li>
          <strong>Google</strong> — if you use Google sign-in, or if analytics are enabled.
        </li>
        <li>
          <strong>AWS</strong> — our cloud infrastructure provider. Your data is hosted in AWS
          data centers.
        </li>
      </ul>
      <p>
        We do not share your data with third parties for advertising or marketing purposes.
      </p>

      <h2>4. Data Retention</h2>
      <p>
        We retain your account information and conversation data for as long as your account is
        active. If you delete your account, we will delete your personal data within 30 days,
        except where we are required to retain it by law (e.g., billing records for 7 years).
      </p>

      <h2>5. Your Rights</h2>
      <p>
        Depending on your location, you may have the following rights regarding your personal data:
      </p>
      <ul>
        <li><strong>Access</strong> — request a copy of the data we hold about you</li>
        <li><strong>Correction</strong> — ask us to correct inaccurate data</li>
        <li><strong>Deletion</strong> — request deletion of your data and account</li>
        <li><strong>Portability</strong> — request your data in a machine-readable format</li>
        <li>
          <strong>Object / Restrict</strong> — object to or restrict certain processing activities
        </li>
      </ul>
      <p>
        To exercise any of these rights, contact us at{' '}
        <a href="mailto:privacy@nash.ai">privacy@nash.ai</a>. We will respond within 30 days.
      </p>
      <p>
        You can delete your conversation history at any time from{' '}
        <strong>Settings → Data Controls → Delete all conversations</strong>.
      </p>

      <h2>6. Security</h2>
      <p>
        We use industry-standard security measures including HTTPS encryption in transit, hashed
        passwords, short-lived authentication tokens, and access controls. All secrets are stored
        in AWS Systems Manager Parameter Store — not in environment variables or source code.
      </p>
      <p>
        No system is perfectly secure. If you discover a security vulnerability, please report
        it responsibly to <a href="mailto:security@nash.ai">security@nash.ai</a>.
      </p>

      <h2>7. Children's Privacy</h2>
      <p>
        The Service is not directed to children under 13. We do not knowingly collect personal
        data from children under 13. If you believe a child has provided us with personal data,
        contact us and we will delete it.
      </p>

      <h2>8. International Transfers</h2>
      <p>
        Your data is stored and processed in the United States. If you are located in the EU or
        UK, your data is transferred to the US subject to appropriate safeguards (e.g., standard
        contractual clauses with our sub-processors).
      </p>

      <h2>9. California Privacy Rights (CCPA)</h2>
      <p>
        California residents have additional rights under the CCPA, including the right to know
        what personal information is collected, the right to delete, and the right to opt out of
        the sale of personal information. We do not sell personal information. To exercise your
        rights, contact <a href="mailto:privacy@nash.ai">privacy@nash.ai</a>.
      </p>

      <h2>10. Changes to This Policy</h2>
      <p>
        We may update this Privacy Policy from time to time. When we make material changes, we
        will update the "Last updated" date above and notify you via email or an in-app notice.
        Continued use of the Service after changes take effect constitutes your acceptance of the
        updated policy.
      </p>

      <h2>11. Contact Us</h2>
      <p>
        If you have questions about this Privacy Policy or your data, please contact us at{' '}
        <a href="mailto:privacy@nash.ai">privacy@nash.ai</a>.
      </p>
    </LegalLayout>
  );
}
