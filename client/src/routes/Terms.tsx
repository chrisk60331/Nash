import LegalLayout from './LegalLayout';

export default function Terms() {
  return (
    <LegalLayout title="Terms of Service" lastUpdated="March 8, 2026">
      <p>
        These Terms of Service ("Terms") govern your use of Nash, an AI chat platform operated
        by Backboard.io, Inc. ("Nash", "we", "us"). By creating an account or using the Service,
        you agree to these Terms. If you do not agree, do not use the Service.
      </p>

      <h2>1. The Service</h2>
      <p>
        Nash provides access to a variety of AI language models through a unified chat interface.
        Features include conversation history, file uploads, custom AI agents, and a model
        marketplace. Access to certain models and features requires a paid subscription.
      </p>

      <h2>2. Eligibility</h2>
      <p>
        You must be at least 13 years old to use Nash. If you are under 18, you represent that
        you have your parent or guardian's permission. By using the Service, you represent that
        you have the legal capacity to enter into these Terms.
      </p>

      <h2>3. Your Account</h2>
      <p>
        You are responsible for maintaining the confidentiality of your account credentials and
        for all activity that occurs under your account. Notify us immediately at{' '}
        <a href="mailto:support@nash.ai">support@nash.ai</a> if you suspect unauthorized access.
      </p>
      <p>
        You may not share your account with others or create accounts on behalf of others without
        their consent. We may suspend or terminate accounts that we believe are being misused.
      </p>

      <h2>4. Acceptable Use</h2>
      <p>You agree not to use the Service to:</p>
      <ul>
        <li>Generate or distribute illegal, harmful, or abusive content</li>
        <li>Harass, threaten, or impersonate others</li>
        <li>Attempt to bypass safety systems or prompt injection attacks</li>
        <li>Scrape, reverse-engineer, or resell the Service without authorization</li>
        <li>Use the Service to build a competing product without our written consent</li>
        <li>Violate any applicable law or the terms of any underlying AI model provider</li>
        <li>Submit content that infringes any third-party intellectual property rights</li>
        <li>
          Engage in excessive automated usage that degrades service quality for other users
        </li>
      </ul>
      <p>
        We reserve the right to terminate access for violations of this section without notice.
      </p>

      <h2>5. Subscriptions and Billing</h2>
      <p>
        Nash offers Free, Plus, and Pro subscription plans. Paid plans are billed monthly in
        advance. All billing is processed by Stripe. By subscribing, you authorize us to charge
        your payment method on a recurring basis.
      </p>
      <p>
        Token usage counts against your plan's monthly allowance. If your plan includes overage
        billing, usage beyond your allowance will be charged at the applicable overage rate.
        You can view current pricing and token limits in the Billing section of your account.
      </p>
      <p>
        You may cancel your subscription at any time from the Billing page. Cancellation takes
        effect at the end of your current billing period. We do not offer refunds for partial
        billing periods unless required by law.
      </p>
      <p>
        We reserve the right to change pricing with 30 days' notice. Continued use after a price
        change takes effect constitutes acceptance of the new pricing.
      </p>

      <h2>6. Your Content</h2>
      <p>
        You retain ownership of the content you submit to the Service. By submitting content, you
        grant us a limited license to process and store it solely to provide the Service to you.
      </p>
      <p>
        You represent that your content does not violate any third-party rights or applicable law.
        We do not use your conversation content to train AI models.
      </p>

      <h2>7. AI-Generated Content</h2>
      <p>
        The AI models accessible through Nash are provided by third parties (OpenAI, Anthropic,
        Google, Cohere, and others). AI outputs may be inaccurate, incomplete, or outdated. You
        are responsible for verifying any AI-generated information before relying on it for
        important decisions. Nash does not warrant the accuracy of AI outputs.
      </p>

      <h2>8. Intellectual Property</h2>
      <p>
        Nash and its original content, features, and functionality are owned by Backboard.io, Inc.
        and protected by applicable intellectual property laws. You may not copy, modify, or
        distribute any part of the Service without our written permission.
      </p>

      <h2>9. Disclaimer of Warranties</h2>
      <p>
        THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND,
        EXPRESS OR IMPLIED, INCLUDING WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
        PURPOSE, OR NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED,
        ERROR-FREE, OR SECURE.
      </p>

      <h2>10. Limitation of Liability</h2>
      <p>
        TO THE MAXIMUM EXTENT PERMITTED BY LAW, BACKBOARD.IO, INC. SHALL NOT BE LIABLE FOR ANY
        INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF
        PROFITS OR DATA, ARISING FROM YOUR USE OF THE SERVICE. OUR TOTAL LIABILITY FOR ANY CLAIM
        ARISING FROM THESE TERMS SHALL NOT EXCEED THE AMOUNT YOU PAID US IN THE 12 MONTHS
        PRECEDING THE CLAIM.
      </p>

      <h2>11. Indemnification</h2>
      <p>
        You agree to indemnify and hold harmless Backboard.io, Inc. and its officers, directors,
        and employees from any claims, damages, or expenses arising from your use of the Service,
        your content, or your violation of these Terms.
      </p>

      <h2>12. Termination</h2>
      <p>
        We may suspend or terminate your access to the Service at any time for any reason,
        including violation of these Terms. You may terminate your account at any time by
        contacting <a href="mailto:support@nash.ai">support@nash.ai</a>. Upon termination, your
        right to use the Service ceases immediately. Provisions that by their nature should
        survive termination (liability, indemnification, disputes) will do so.
      </p>

      <h2>13. Governing Law</h2>
      <p>
        These Terms are governed by the laws of the State of Delaware, USA, without regard to
        its conflict-of-law provisions. Any dispute arising from these Terms shall be resolved
        through binding arbitration in Delaware, except that either party may seek injunctive
        relief in a court of competent jurisdiction.
      </p>

      <h2>14. Changes to These Terms</h2>
      <p>
        We may update these Terms from time to time. When we make material changes, we will
        update the "Last updated" date and notify you via email or in-app notice at least 14 days
        before the changes take effect. Continued use after the effective date constitutes
        acceptance.
      </p>

      <h2>15. Contact</h2>
      <p>
        Questions about these Terms? Contact us at{' '}
        <a href="mailto:support@nash.ai">support@nash.ai</a> or write to:
      </p>
      <p>
        Backboard.io, Inc.<br />
        Legal Department<br />
        <a href="mailto:legal@nash.ai">legal@nash.ai</a>
      </p>
    </LegalLayout>
  );
}
