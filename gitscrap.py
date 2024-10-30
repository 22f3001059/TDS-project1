import os
import requests
import pandas as pd
import time
import logging
from typing import List, Dict, Any

class GitHubScraper:
    def __init__(self, token: str):
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = 'https://api.github.com'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _make_request(self, url: str, params: dict = None) -> Dict:
        while True:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                sleep_time = max(reset_time - time.time(), 0) + 1
                self.logger.warning(f"Rate limit hit. Sleeping for {sleep_time} seconds")
                time.sleep(sleep_time)
            else:
                self.logger.error(f"Error {response.status_code}: {response.text}")
                response.raise_for_status()

    def clean_company_name(self, company: str) -> str:
        if not company:
            return ""
        cleaned = company.strip().lstrip('@')
        return cleaned.upper()

    def search_users(self, location: str, min_followers: int) -> List[Dict]:
        users = []
        page = 1
        while True:
            self.logger.info(f"Fetching users page {page}")
            query = f"location:{location} followers:>={min_followers}"
            params = {'q': query, 'per_page': 100, 'page': page}
            url = f"{self.base_url}/search/users"
            response = self._make_request(url, params)
            if not response['items']:
                break
            for user in response['items']:
                user_data = self._make_request(user['url'])
                cleaned_data = {
                    'login': user_data['login'],
                    'name': user_data['name'] if user_data['name'] else "",
                    'company': self.clean_company_name(user_data.get('company')),
                    'location': user_data['location'] if user_data['location'] else "",
                    'email': user_data['email'] if user_data['email'] else "",
                    'hireable': user_data['hireable'] if user_data['hireable'] is not None else False,
                    'bio': user_data['bio'] if user_data['bio'] else "",
                    'public_repos': user_data['public_repos'],
                    'followers': user_data['followers'],
                    'following': user_data['following'],
                    'created_at': user_data['created_at']
                }
                users.append(cleaned_data)
            page += 1
        return users

    def get_user_repositories(self, username: str, max_repos: int = 500) -> List[Dict]:
        repos = []
        page = 1
        while len(repos) < max_repos:
            self.logger.info(f"Fetching repositories for {username}, page {page}")
            params = {'sort': 'pushed', 'direction': 'desc', 'per_page': 100, 'page': page}
            url = f"{self.base_url}/users/{username}/repos"
            response = self._make_request(url, params)
            if not response:
                break
            for repo in response:
                repo_data = {
                    'login': username,
                    'full_name': repo['full_name'],
                    'created_at': repo['created_at'],
                    'stargazers_count': repo['stargazers_count'],
                    'watchers_count': repo['watchers_count'],
                    'language': repo['language'] if repo['language'] else "",
                    'has_projects': repo['has_projects'],
                    'has_wiki': repo['has_wiki'],
                    'license_name': repo['license']['key'] if repo.get('license') else ""
                }
                repos.append(repo_data)
            if len(response) < 100:
                break
            page += 1
        return repos[:max_repos]

def main():
    token = input("Enter your GitHub token: ").strip()
    if not token:
        print("Token is required. Exiting...")
        return

    scraper = GitHubScraper(token)
    users = scraper.search_users(location='Berlin', min_followers=200)
    
    # Save users to CSV in the same directory as the script
    users_file_path = os.path.join(os.path.dirname(__file__), 'users.csv')
    users_df = pd.DataFrame(users)
    users_df.to_csv(users_file_path, index=False)
    
    # Get repositories for each user
    all_repos = []
    for user in users:
        repos = scraper.get_user_repositories(user['login'])
        all_repos.extend(repos)
    
    # Save repositories to CSV in the same directory as the script
    repos_file_path = os.path.join(os.path.dirname(__file__), 'repositories.csv')
    repos_df = pd.DataFrame(all_repos)
    repos_df.to_csv(repos_file_path, index=False)
    
    print(f"Scraped {len(users)} users and {len(all_repos)} repositories")
    
    # Create README.md in the same directory as the script
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    with open(readme_path, 'w') as f:
        f.write(f"""# GitHub Users in Berlin

This directory contains data about GitHub users in Berlin with over 200 followers and their repositories.

## Files

1. `users.csv`: Contains information about {len(users)} GitHub users in Berlin with over 200 followers
2. `repositories.csv`: Contains information about {len(all_repos)} public repositories from these users
3. `gitscrap.py`: Python script used to collect this data

## Data Collection

- Data collected using GitHub API
- Date of collection: {time.strftime('%Y-%m-%d')}
- Only included users with 200+ followers
- Up to 500 most recently pushed repositories per user
""")

if __name__ == "__main__":
    main()
