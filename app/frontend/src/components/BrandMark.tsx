type BrandMarkProps = {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  tone?: 'light' | 'dark';
};

const SIZES = {
  sm: 'text-xl',
  md: 'text-2xl',
  lg: 'text-4xl',
};

/** Marca institucional. A assinatura aparece uma única vez por tela. */
export default function BrandMark({
  className = '',
  size = 'md',
  tone = 'light',
}: BrandMarkProps) {
  return (
    <span
      className={`${SIZES[size]} leading-none tracking-[-0.03em] ${tone === 'light' ? 'text-white' : 'text-black'} ${className}`}
      style={{ fontFamily: "'Montserrat', sans-serif", fontWeight: 500 }}
      aria-label="ness."
    >
      ness<span style={{ color: '#00ADE8' }}>.</span>
    </span>
  );
}
