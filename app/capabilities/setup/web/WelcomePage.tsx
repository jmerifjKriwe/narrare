/**
 * The welcome screen's place in the route table — the `/` gate's incomplete
 * branch. The port task fills this file with the `welcome-atelier` draft;
 * until then the interim SetupPage stands in. A module of its own so the
 * gate's two branches stay distinguishable while both are placeholders
 * (routes.test.tsx mocks the pair to pin the choice itself).
 */
export { SetupPage as WelcomePage } from "./SetupPage";
