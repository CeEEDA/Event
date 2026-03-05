export const Logo = ({ size = "normal" }) => {
  const sizes = {
    small: "h-6",
    normal: "h-10 md:h-12",
    large: "h-12 md:h-16"
  };

  return (
    <img 
      src="https://customer-assets.emergentagent.com/job_client-file-portal/artifacts/35th6vn9_cropped-logo.webp" 
      alt="Eventenergie Deutschland" 
      className={`${sizes[size]} object-contain`}
    />
  );
};
