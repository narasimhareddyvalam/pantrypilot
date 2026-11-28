// Sample data for the phone page. The page uses it until the pantry API
// and the assistant API are ready (see the switches at the top of app.js).

// A few pantry items, in the same shape the pantry API will use.
const SAMPLE_PANTRY = [
  { id: 1, productName: "Rolled oats", labelType: "best_before", date: "2027-01-05" },
  { id: 2, productName: "Greek yogurt", labelType: "expiration", date: "2026-12-03" },
  { id: 3, productName: "Canned tomatoes", labelType: "best_before", date: "2028-06-30" },
  { id: 4, productName: "Honey", labelType: null, date: null },
  { id: 5, productName: "Whole milk", labelType: "sell_by", date: "2026-11-30" },
];

// Short answers about label words. They explain what the words mean and
// never promise that food is safe to eat.
const SAMPLE_ANSWERS = {
  best_before: "\"Best before\" is about quality. The maker says the food is at its best until that date. It isn't a safety date, so look at the food and follow the storage instructions on the package.",
  expiration: "\"Use by\" or \"expires\" is the last day the maker says to use the product. Follow the storage instructions on the package, and don't use it after that date.",
  sell_by: "\"Sell by\" tells the store how long to keep the product on the shelf. It's meant for the store, not a date for you to finish it by.",
  manufacturing: "A \"made on\" or MFG date shows when the product was made. It doesn't say when it runs out, unless the package also gives a shelf life.",
  fallback: "I can explain label dates and tell you the dates on items in your pantry. Try asking \"What does best before mean?\"",
};
