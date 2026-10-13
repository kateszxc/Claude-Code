// Countries offered in the location picker (most common e-commerce markets first).
export const COUNTRIES = [
  "United States", "Canada", "United Kingdom", "Australia", "New Zealand", "Ireland",
  "Germany", "France", "Netherlands", "Spain", "Italy", "Sweden", "Denmark", "Norway", "Finland",
  "Belgium", "Switzerland", "Austria", "Portugal", "Poland", "Japan", "South Korea", "Singapore",
  "Philippines", "Indonesia", "Malaysia", "Thailand", "Vietnam", "India", "United Arab Emirates",
  "Saudi Arabia", "Israel", "Turkey", "South Africa", "Nigeria", "Kenya", "Mexico", "Brazil",
  "Argentina", "Colombia", "Chile",
];

// States / provinces for countries where a dropdown helps; other countries get a text box.
export const REGIONS: Record<string, string[]> = {
  "United States": [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
    "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
  ],
  Canada: [
    "Alberta", "British Columbia", "Manitoba", "New Brunswick", "Newfoundland and Labrador",
    "Nova Scotia", "Ontario", "Prince Edward Island", "Quebec", "Saskatchewan",
  ],
  "United Kingdom": ["England", "Scotland", "Wales", "Northern Ireland"],
  Australia: [
    "New South Wales", "Victoria", "Queensland", "Western Australia", "South Australia",
    "Tasmania", "Australian Capital Territory", "Northern Territory",
  ],
};
