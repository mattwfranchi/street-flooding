
// Stan code below works and has been reviewed but does not implement a proper ICAR prior. Set variable use_ICAR_prior to 0 if you don't want to use one at all. 
// I think it might also be principled to set the ICAR prior weight to 0.5, https://mc-stan.org/users/documentation/case-studies/icar_stan.html. 
// This assumes we have location information for each annotation. 
data {
  int<lower=0> N; // number of Census tracts. 
  int<lower=0> N_edges; // number of edges in the graph (i.e. number of pairs of adjacent Census tracts). 
  array[N_edges] int<lower=1, upper=N> node1; // node1[i] adjacent to node2[i]
  array[N_edges] int<lower=1, upper=N> node2; // and node1[i] < node2[i]
  vector[N] n_images_by_area; // vector with one entry per Census tract of the number of images in that tract. 
  vector[N] n_classified_positive_by_area; // vector with one entry per Census tract of number of images classified positive. 
  vector[N] n_classified_positive_annotated_positive_by_area;
  vector[N] n_classified_positive_annotated_negative_by_area;
  vector[N] n_classified_negative_annotated_positive_by_area;
  vector[N] n_classified_negative_annotated_negative_by_area;
  array[N] int<lower=0> n_non_annotated_by_area;
  array[N] int<lower=0> n_non_annotated_by_area_classified_positive;

  int<lower=0,upper=1> use_ICAR_prior; // 1 if you want to use ICAR prior, 0 if you don't. ICAR prior basically smooths the data. 
  real <lower=0> ICAR_prior_weight; // weight of ICAR prior.

  // external covariate matrix. This part is new. 
  int<lower=1> n_external_covariates; // number of external covariates.
  matrix[N, n_external_covariates] external_covariates; // matrix with one row per Census tract and one column per external covariate.
}
parameters {
  vector[N] phi;
  real<upper=0> phi_offset; // this is the mean from which phis are drawn. Upper bound at 0 to rule out bad modes and set prior that true positives are rare. 
  ordered[2] logit_p_y_1_given_y_hat; // ordered to impose the constraint that p_y_1_given_y_hat_0 < p_y_1_given_y_hat_1.
  // vector[n_external_covariates] external_covariate_slopes; // coefficients for the external covariates.
  // vector[n_external_covariates] external_covariate_intercepts; // intercepts for the external covariates.
  real<lower=0> phi_sigma; 
  vector[n_external_covariates] external_covariate_beta; // coefficients for the external covariates.
}
transformed parameters {
    real p_y_1_given_y_hat_0 = inv_logit(logit_p_y_1_given_y_hat[1]);
    real p_y_1_given_y_hat_1 = inv_logit(logit_p_y_1_given_y_hat[2]);
    vector[N] p_y = inv_logit(phi);
    real empirical_p_yhat = sum(n_classified_positive_by_area) * 1.0 / sum(n_images_by_area);
    real p_y_hat_1_given_y_1 = empirical_p_yhat * p_y_1_given_y_hat_1 / (empirical_p_yhat * p_y_1_given_y_hat_1 + (1 - empirical_p_yhat) * p_y_1_given_y_hat_0);
    real p_y_hat_1_given_y_0 = empirical_p_yhat * (1 - p_y_1_given_y_hat_1) / (empirical_p_yhat * (1 - p_y_1_given_y_hat_1) + (1 - empirical_p_yhat) * (1 - p_y_1_given_y_hat_0));
    vector[N] at_least_one_positive_image_by_area = (1 - pow(1 - p_y, n_images_by_area));
    vector[N] at_least_one_positive_image_by_area_if_you_have_100_images = (1 - pow(1 - p_y, 100));
    // set at_least_one_positive_image to 1 if there is at least one annotated positive image in the Census tract.
    for(i in 1:N) {
      if ((n_classified_positive_annotated_positive_by_area[i] > 0) || (n_classified_negative_annotated_positive_by_area[i] > 0)) {
        at_least_one_positive_image_by_area[i] = 1;
        at_least_one_positive_image_by_area_if_you_have_100_images[i] = 1;
      }
    }
}
model {
  // You can't just scale ICAR priors by random numbers; the only principled value for ICAR_prior_weight is 0.5. 
  // https://stats.stackexchange.com/questions/333258/strength-parameter-in-icar-spatial-model
  // still, there's no computational reason you can't use another value. 
  if (use_ICAR_prior == 1) {
    target += -ICAR_prior_weight * dot_self(phi[node1] - phi[node2]);
  }
  
  phi_offset ~ normal(0, 2);
  phi_sigma ~ normal(0, 1);
  external_covariate_beta ~ normal(0, 1);
  phi ~ normal(phi_offset + external_covariates * external_covariate_beta, phi_sigma);
  // phi ~ normal(phi_offset, 1); 
  // model the classification results by Census tract for the UNANNOTATED images. 
  // note that this binomial statement should be equivalent a statement which increments the target directly, but that's more verbose. 
  n_non_annotated_by_area_classified_positive ~ binomial(n_non_annotated_by_area, p_y .* p_y_hat_1_given_y_1 + (1 - p_y) .* p_y_hat_1_given_y_0);
  
  // model the annotation results by Census tract. 
  target += (sum(n_classified_positive_annotated_positive_by_area .* log(p_y * p_y_hat_1_given_y_1))
      + sum(n_classified_positive_annotated_negative_by_area .* log((1 - p_y) * p_y_hat_1_given_y_0))
    + sum(n_classified_negative_annotated_positive_by_area .* log(p_y * (1 - p_y_hat_1_given_y_1)))
    + sum(n_classified_negative_annotated_negative_by_area .* log((1 - p_y) * (1 - p_y_hat_1_given_y_0))));

  // external_covariate_intercepts ~ normal(0, 1);
   // external_covariate_slopes ~ normal(0, 100);
  // for(i in 1:n_external_covariates){
  //   binary_external_covariates[,i] ~ bernoulli_logit(external_covariate_intercepts[i] + external_covariate_slopes[i] * p_y);
  // }
  
}