type LogoProps = {
  variant?: 'primary' | 'compact' | 'symbol' | 'wordmark' | 'wordmarkWhite' | 'mono';
  surface?: 'dark' | 'light';
  className?: string;
  alt?: string;
};

const logoVariants = {
  primary: '/assets/Logotipo%20principal%20%E2%80%94%20s%C3%ADmbolo%20%2B%20nome.png',
  compact: '/assets/Vers%C3%A3o%20horizontal%20compacta.png',
  symbol: '/assets/S%C3%ADmbolo%20isolado.png',
  wordmark: '/assets/Wordmark%20%E2%80%94%20somente%20IMPERIAL%20PACK.png',
  wordmarkWhite: '/assets/Wordmark%20%E2%80%94%20Branco.png',
  mono: '/assets/Vers%C3%A3o%20monocrom%C3%A1tica.png',
};

export function Logo({
  variant = 'primary',
  surface = 'dark',
  className = '',
  alt = 'Imperial Pack',
}: LogoProps) {
  const selectedVariant = surface === 'light' ? 'mono' : variant;
  const logoPath = logoVariants[selectedVariant] ?? logoVariants.primary;

  return (
    <img
      src={logoPath}
      alt={alt}
      className={className}
      style={{ display: 'block', maxWidth: '100%', height: 'auto', objectFit: 'contain' }}
    />
  );
}
