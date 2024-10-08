import pandas as pd
import stan
import numpy as np
from scipy.stats import pearsonr
from scipy.special import expit
import matplotlib.pyplot as plt
import arviz as az
import random

def read_real_data(single_compartment_for_debugging=False):
    df = pd.read_csv("flooding_ct_dataset.csv")
    df[['total_images','positive_images']] = df[['total_images','positive_images']].astype(int).fillna(0)
    N = len(df)
    n_images_by_area = df['total_images'].values
    n_classified_positive_by_area = df['positive_images'].values 

    # Generate adjacency matrix and neighborhood structure. This is just empty by default. 
    node1 = []
    node2 = []

    TOTAL_ANNOTATED_CLASSIFIED_NEGATIVE = 500
    TOTAL_ANNOTATED_CLASSIFIED_POSITIVE = 500
    TOTAL_ANNOTATED_CLASSIFIED_NEGATIVE_TRUE_POSITIVE = 3
    TOTAL_ANNOTATED_CLASSIFIED_POSITIVE_TRUE_POSITIVE = 329


    if single_compartment_for_debugging:
        N = 1
        n_images_by_area = [sum(n_images_by_area)]
        n_classified_positive_by_area = [sum(n_classified_positive_by_area)]

    return {'observed_data': {
                'N': N, 'N_edges': len(node1), 'node1': node1, 'node2': node2, 
                'n_images_by_area': n_images_by_area,
                'n_classified_positive_by_area': n_classified_positive_by_area, 
                'total_annotated_classified_negative': TOTAL_ANNOTATED_CLASSIFIED_NEGATIVE,
                'total_annotated_classified_positive': TOTAL_ANNOTATED_CLASSIFIED_POSITIVE,
                'total_annotated_classified_negative_true_positive': TOTAL_ANNOTATED_CLASSIFIED_NEGATIVE_TRUE_POSITIVE,
                'total_annotated_classified_positive_true_positive': TOTAL_ANNOTATED_CLASSIFIED_POSITIVE_TRUE_POSITIVE
            }
            }

def generate_simulated_data(N, images_per_location, 
                            total_annotated_classified_negative, 
                            total_annotated_classified_positive, 
                            icar_prior_setting, 
                            annotations_have_locations):
    """
    Generate simulated data for the model.
    """    
    node1 = []
    node2 = []
    for i in range(N):
        for j in range(i+1, N):
            if np.random.rand() < 0.1:
                node1.append(i + 1) # one indexing for Stan. 
                node2.append(j + 1)
    phi_offset = random.random() * -3 - 1 # mean of phi.

    # these only matter for CAR model. https://mc-stan.org/users/documentation/case-studies/mbjoseph-CARStan.html
    D = np.zeros((N, N))
    W = np.zeros((N, N))
    for i in range(len(node1)):
        D[node1[i] - 1, node1[i] - 1] += 1
        D[node2[i] - 1, node2[i] - 1] += 1
        W[node1[i] - 1, node2[i] - 1] = 1
        W[node2[i] - 1, node1[i] - 1] = 1
    B = np.linalg.inv(D) @ W
    tau = np.random.gamma(scale=0.2, shape=2)
    alpha = np.random.random()
    sigma = np.linalg.inv(tau * D @ (np.eye(N) - alpha * B))
    if icar_prior_setting != 'none':    
        phi = np.random.multivariate_normal(mean=np.zeros(N), cov=sigma)
    else:
        phi = np.random.normal(loc=0, size=N) # this uses no icar prior, just draws everything independently. 
    p_Y = expit(phi + phi_offset)
    n_images_by_area = np.random.poisson(images_per_location, N)
    p_y_hat_1_given_y_1 = random.random() * 0.5 + 0.2
    p_y_hat_1_given_y_0 = random.random() * 0.01 + 0.01

    n_true_positive_by_area = []
    n_true_positive_classified_positive_by_area = []
    n_true_positive_classified_negative_by_area = []
    n_true_negative_classified_positive_by_area = []
    n_true_negative_classified_negative_by_area = []
    n_classified_positive_by_area = []
    
    for i in range(N):
        n_true_positive_by_area.append(np.random.binomial(n_images_by_area[i], p_Y[i]))
        n_true_positive_classified_positive_by_area.append(np.random.binomial(n_true_positive_by_area[i], p_y_hat_1_given_y_1))
        n_true_positive_classified_negative_by_area.append(n_true_positive_by_area[i] - n_true_positive_classified_positive_by_area[i])
        n_true_negative_classified_positive_by_area.append(np.random.binomial(n_images_by_area[i] - n_true_positive_by_area[i], p_y_hat_1_given_y_0))
        n_true_negative_classified_negative_by_area.append(n_images_by_area[i] - n_true_positive_by_area[i] - n_true_negative_classified_positive_by_area[i])
        n_classified_positive_by_area.append(n_true_positive_classified_positive_by_area[i] + n_true_negative_classified_positive_by_area[i])
    empirical_p_yhat = sum(n_classified_positive_by_area) * 1.0 / sum(n_images_by_area)
    empirical_p_y = sum(n_true_positive_by_area) * 1.0 / sum(n_images_by_area)
    p_y_1_given_y_hat_1 = p_y_hat_1_given_y_1 * empirical_p_y / empirical_p_yhat
    p_y_1_given_y_hat_0 = (1 - p_y_hat_1_given_y_1) * empirical_p_y / (1 - empirical_p_yhat)
    print("empirical_p_y", empirical_p_y)
    print("empirical_p_yhat", empirical_p_yhat)
    print("p_y_hat_1_given_y_1", p_y_hat_1_given_y_1)
    print("p_y_hat_1_given_y_0", p_y_hat_1_given_y_0)
    print("p_y_1_given_y_hat_1", p_y_1_given_y_hat_1)
    print("p_y_1_given_y_hat_0", p_y_1_given_y_hat_0)

    if not annotations_have_locations:
        total_annotated_classified_negative_true_positive = np.random.binomial(total_annotated_classified_negative, p_y_1_given_y_hat_0)
        total_annotated_classified_positive_true_positive = np.random.binomial(total_annotated_classified_positive, p_y_1_given_y_hat_1)
        print("number of annotated classified negative which were positive: %i/%i" % (total_annotated_classified_negative_true_positive, total_annotated_classified_negative))
        print("number of annotated classified positive which were positive: %i/%i" % (total_annotated_classified_positive_true_positive, total_annotated_classified_positive))
        observed_data = {'N':N, 'N_edges':len(node1), 'node1':node1, 'node2':node2, 
                             'n_images_by_area':n_images_by_area, 'n_classified_positive_by_area':n_classified_positive_by_area, 
                             'total_annotated_classified_negative':total_annotated_classified_negative,
                                'total_annotated_classified_positive':total_annotated_classified_positive,
                                'total_annotated_classified_negative_true_positive':total_annotated_classified_negative_true_positive,
                                'total_annotated_classified_positive_true_positive':total_annotated_classified_positive_true_positive}
    else:
        # distribute the annotations across the areas: positive classifications first. 
        n_classified_positive_annotated_by_area = np.random.multinomial(total_annotated_classified_positive, np.array(n_classified_positive_by_area)/sum(n_classified_positive_by_area))
        assert n_classified_positive_annotated_by_area.sum() == total_annotated_classified_positive
        # then negatives. 
        ps = np.array(n_images_by_area) - np.array(n_classified_positive_by_area)
        ps = ps / sum(ps)
        n_classified_negative_annotated_by_area = np.random.multinomial(total_annotated_classified_negative, ps)
        assert n_classified_negative_annotated_by_area.sum() == total_annotated_classified_negative

        # the first 5 categories below are disjoint (they should not contain the same images). 
        n_classified_positive_annotated_positive_by_area = []
        n_classified_positive_annotated_negative_by_area = []
        n_classified_negative_annotated_positive_by_area = []
        n_classified_negative_annotated_negative_by_area = []
        n_non_annotated_by_area = []
        n_non_annotated_by_area_classified_positive = []
        for i in range(N):
            if n_classified_positive_annotated_by_area[i] > 0:
                vector_to_sample = [1] * n_true_positive_classified_positive_by_area[i] + [0] * n_true_negative_classified_positive_by_area[i]
                samples = np.random.choice(vector_to_sample, n_classified_positive_annotated_by_area[i], replace=False)
                assert len(samples) == n_classified_positive_annotated_by_area[i]
                n_classified_positive_annotated_positive_by_area.append(sum(samples))
                n_classified_positive_annotated_negative_by_area.append(n_classified_positive_annotated_by_area[i] - sum(samples))
            else:
                n_classified_positive_annotated_positive_by_area.append(0)
                n_classified_positive_annotated_negative_by_area.append(0)
            if n_classified_negative_annotated_by_area[i] > 0:
                vector_to_sample = [1] * n_true_positive_classified_negative_by_area[i] + [0] * n_true_negative_classified_negative_by_area[i]
                samples = np.random.choice(vector_to_sample, n_classified_negative_annotated_by_area[i], replace=False)
                assert len(samples) == n_classified_negative_annotated_by_area[i]
                n_classified_negative_annotated_positive_by_area.append(sum(samples))
                n_classified_negative_annotated_negative_by_area.append(n_classified_negative_annotated_by_area[i] - sum(samples))
            else:
                n_classified_negative_annotated_positive_by_area.append(0)
                n_classified_negative_annotated_negative_by_area.append(0)
            n_non_annotated_by_area.append(n_images_by_area[i] - n_classified_negative_annotated_by_area[i] - n_classified_positive_annotated_by_area[i])
            n_non_annotated_by_area_classified_positive.append(n_classified_positive_by_area[i] - n_classified_positive_annotated_by_area[i])
            assert n_non_annotated_by_area[i] + n_classified_positive_annotated_positive_by_area[i] + n_classified_positive_annotated_negative_by_area[i] + n_classified_negative_annotated_positive_by_area[i] + n_classified_negative_annotated_negative_by_area[i] == n_images_by_area[i]

        observed_data = {'N':N, 'N_edges':len(node1), 'node1':node1, 'node2':node2, 
                             'n_images_by_area':n_images_by_area, 'n_classified_positive_by_area':n_classified_positive_by_area, 
                                'n_classified_positive_annotated_positive_by_area':n_classified_positive_annotated_positive_by_area,
                                'n_classified_positive_annotated_negative_by_area':n_classified_positive_annotated_negative_by_area,
                                'n_classified_negative_annotated_positive_by_area':n_classified_negative_annotated_positive_by_area,
                                'n_classified_negative_annotated_negative_by_area':n_classified_negative_annotated_negative_by_area, 
                                'n_non_annotated_by_area':n_non_annotated_by_area,
                                'n_non_annotated_by_area_classified_positive':n_non_annotated_by_area_classified_positive}

    return {'observed_data':observed_data,
            'parameters':{'phi':phi, 'phi_offset':phi_offset, 
                          'p_y_1_given_y_hat_1':p_y_1_given_y_hat_1,
                            'p_y_1_given_y_hat_0':p_y_1_given_y_hat_0, 
                            'p_y_hat_1_given_y_1':p_y_hat_1_given_y_1,
                            'p_y_hat_1_given_y_0':p_y_hat_1_given_y_0, 
                            'p_Y':p_Y, 
                            'tau':tau, 'alpha':alpha, 'sigma':sigma}}